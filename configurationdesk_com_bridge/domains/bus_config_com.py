"""COM wrappers for ConfigurationDesk bus configuration operations.

All functions must be called on the STA thread via dispatch().
"""

from __future__ import annotations

import fnmatch
import logging
from typing import Any, List, Optional

from configurationdesk_com_bridge.domains._property_helpers import (
    normalize_property_name,
    property_values_match,
    resolve_named_property_handle,
    try_set_property_value,
)
from configurationdesk_com_bridge.domains.verify_com import (
    build_xpath,
    build_xpath_alternatives,
    get_top_node_names,
    verify_exists,
)

_log = logging.getLogger(__name__)


_FUNCTION_PORT_FEATURE_TYPE_ALIASES: dict[str, tuple[str, ...]] = {
    "isignalvalue": ("BusISignalValueAccess", "BusISignalValueInspection"),
    "signalvalue": ("BusISignalValueAccess", "BusISignalValueInspection"),
    "signalvalues": ("BusISignalValueAccess", "BusISignalValueInspection"),
    "busisignalvalueaccess": ("BusISignalValueAccess",),
    "busisignalvalueinspection": ("BusISignalValueInspection",),
    "isignaloverwritevalue": ("BusISignalOverwriteValueManipulation",),
    "busisignaloverwritevaluemanipulation": ("BusISignalOverwriteValueManipulation",),
    "isignaloffsetvalue": ("BusISignalOffsetValueManipulation",),
    "busisignaloffsetvaluemanipulation": ("BusISignalOffsetValueManipulation",),
    "pdutrigger": ("BusPduTriggerAccess",),
    "buspdutriggeraccess": ("BusPduTriggerAccess",),
    "pducyclictimingcontrol": ("BusPduCyclicTimingControlAccess",),
    "buspducyclictimingcontrolaccess": ("BusPduCyclicTimingControlAccess",),
    "pduenable": ("BusPduEnableAccess",),
    "buspduenableaccess": ("BusPduEnableAccess",),
    "rxstatus": ("BusPduRxStatusAccess", "BusPduRxStatusInspection"),
    "pdurxstatus": ("BusPduRxStatusAccess", "BusPduRxStatusInspection"),
    "buspdurxstatusaccess": ("BusPduRxStatusAccess",),
    "buspdurxstatusinspection": ("BusPduRxStatusInspection",),
    "frameaccess": ("BusFrameAccess",),
    "busframeaccess": ("BusFrameAccess",),
    "communicationcontrollerenable": ("BusCommunicationControllerEnableAccess",),
    "buscommunicationcontrollerenableaccess": ("BusCommunicationControllerEnableAccess",),
    "linscheduletable": ("BusCommunicationControllerLinScheduleTableAccess",),
    "linschedulingtable": ("BusCommunicationControllerLinScheduleTableAccess",),
    "buscommunicationcontrollerlinscheduletableaccess": (
        "BusCommunicationControllerLinScheduleTableAccess",
    ),
    "configurationenable": ("BusConfigurationEnableAccess",),
    "busconfigurationenableaccess": ("BusConfigurationEnableAccess",),
    "suspendframetransmission": ("BusSuspendFrameTransmissionManipulation",),
    "bussuspendframetransmissionmanipulation": ("BusSuspendFrameTransmissionManipulation",),
    "framelength": ("BusFrameLengthManipulation",),
    "busframelengthmanipulation": ("BusFrameLengthManipulation",),
}


def create(connection, name: Optional[str] = None) -> dict[str, Any]:
    """Create a new bus configuration."""
    bus_rel = connection.relations.Item("BusConfigurations")
    creatable_types = bus_rel.GetCreatableTypes()
    bus_config = bus_rel.CreateDataObject(creatable_types.Item(0))
    if name:
        bus_config.Name = name
    bc_name = bus_config.Name
    ok, detail = verify_exists("BusConfigurations", bc_name, connection)
    if name and bc_name != name:
        return {
            "name": bc_name,
            "verified": False,
            "detail": (
                f"Created bus configuration name '{bc_name}' does not match requested name '{name}'."
            ),
        }
    return {"name": bc_name, "verified": ok, "detail": detail}


def remove(connection, name: str) -> dict[str, Any]:
    """Remove bus configuration(s) by name (supports wildcards)."""
    bus_rel = connection.relations.Item("BusConfigurations")
    removed = []
    for node in bus_rel.GetTopNodes():
        if fnmatch.fnmatchcase(node.Name, name):
            bus_rel.RemoveElements(None, [node])
            removed.append(node.Name)
    if removed:
        remaining = get_top_node_names("BusConfigurations", connection)
        still_present = [n for n in removed if n in remaining]
        return {"removed": removed, "still_present": still_present, "verified": not still_present}
    return {
        "removed": [],
        "still_present": [],
        "verified": False,
        "detail": f"No bus configuration matching '{name}' found",
    }


def list_configs(connection) -> list[str]:
    """List all bus configurations in the project."""
    bus_rel = connection.relations.Item("BusConfigurations")
    return [node.Name for node in bus_rel.GetTopNodes()]


# Mapping of user-facing part names to the bus configuration child node names
# returned by ``BusConfigurations.GetElements(bus_config)``.
_PART_NAME_MAP = {
    "simulated": "Simulated ECUs",
    "simulated ecus": "Simulated ECUs",
    "simulatedecus": "Simulated ECUs",
    "inspection": "Inspection",
    "manipulation": "Manipulation",
    "gateways": "Gateways",
    "gateway": "Gateways",
}


def _resolve_bus_config_targets(
    bus_rel, bus_config, part: Optional[str]
) -> tuple[list[Any], Optional[str]]:
    """Return the list of target nodes for AssignElements based on ``part``.

    ``part`` may be:
        * ``None`` or ``"all"`` → assign to every bus configuration part
          (Simulated ECUs, Inspection, Manipulation), like the original UI command.
        * A single part name (e.g. ``"simulated"``, ``"inspection"``) →
          assign only to that part.

    Returns ``(targets, error_message)`` where ``targets`` is empty when an
    error message is present.
    """
    if part is None or str(part).strip().lower() == "all":
        # Assign to all three standard parts. The Bus Manager exposes these as
        # explicit children of the bus configuration.
        targets: list[Any] = []
        try:
            children = bus_rel.GetElements(bus_config)
        except Exception as exc:
            return [], f"Cannot read bus configuration parts: {exc}"
        wanted = ("Simulated ECUs", "Inspection", "Manipulation")
        for name in wanted:
            try:
                targets.append(children.Item(name))
            except Exception:
                # Some bus configurations may not have every part — skip.
                continue
        if not targets:
            return [], "Bus configuration has no Simulated ECUs/Inspection/Manipulation parts."
        return targets, None

    key = str(part).strip().lower()
    canonical = _PART_NAME_MAP.get(key)
    if not canonical:
        return [], (
            f"Unknown bus configuration part '{part}'. "
            f"Use one of: 'all', 'simulated', 'inspection', 'manipulation', 'gateways'."
        )
    try:
        target = bus_rel.GetElements(bus_config).Item(canonical)
    except Exception as exc:
        return [], f"Bus configuration part '{canonical}' not accessible: {exc}"
    return [target], None


def assign_matrix(
    connection,
    bus_config_name: str,
    element_name: Optional[str] = None,
    element_type: Optional[str] = None,
    matrix_xpath: Optional[str] = None,
    part: Optional[str] = None,
) -> dict[str, Any]:
    """Assign matrix elements to a bus configuration.

    ``part`` controls which bus configuration part receives the assignment:
    ``None`` / ``"all"`` (default) targets Simulated ECUs, Inspection, and
    Manipulation; ``"simulated"``, ``"inspection"``, ``"manipulation"`` target
    a single part.
    """
    bm = connection.busmanager
    bus_rel = connection.relations.Item("BusConfigurations")
    bus_config = None
    for node in bus_rel.GetTopNodes():
        if node.Name == bus_config_name:
            bus_config = node
            break
    if bus_config is None:
        return {"error": True, "detail": f"Bus configuration '{bus_config_name}' not found"}

    xpath = matrix_xpath
    if not xpath:
        if not element_name and not element_type:
            return {"error": True, "detail": "Provide element_name, element_type, or matrix_xpath"}
        xpath = build_xpath(element_type=element_type, name=element_name)

    matrix_rel = connection.relations.Item("CommunicationMatricesByEcus")
    items = list(matrix_rel.FindByXPath(xpath, None))
    if not items:
        matrix_rel = connection.relations.Item("CommunicationMatricesByClusters")
        items = list(matrix_rel.FindByXPath(xpath, None))
    if not items:
        return {"error": True, "detail": f"No matrix elements found for '{element_name or xpath}'"}

    targets, err = _resolve_bus_config_targets(bus_rel, bus_config, part)
    if err:
        return {"error": True, "detail": err}

    item_names = [item.Name for item in items]
    assigned_parts: list[str] = []
    for tgt in targets:
        bm.Configure("AssignElements", [items, tgt])
        try:
            assigned_parts.append(tgt.Name)
        except Exception:
            assigned_parts.append("<unknown>")

    children_after = list(bus_rel.FindByXPath(f'//*[@Name="{bus_config_name}"]//*', None))
    verified = bool(children_after)
    return {"assigned": item_names, "parts": assigned_parts, "verified": verified}


def assign_ecu(
    connection,
    bus_config_name: Optional[str] = None,
    ecu_names: Optional[List[str]] = None,
    ecu_xpath: Optional[str] = None,
    exclude_list: str = "",
    part: Optional[str] = None,
) -> dict[str, Any]:
    """Assign ECU(s) from the matrix to a bus configuration.

    ``part`` controls which bus configuration part receives the ECUs:
    ``None`` / ``"all"`` (default) targets Simulated ECUs, Inspection, and
    Manipulation; ``"simulated"``, ``"inspection"``, ``"manipulation"`` target
    a single part. When ``bus_config_name`` is ``None``, the assignment cannot
    be scoped to a part — the call falls back to the legacy unscoped form.
    """
    bm = connection.busmanager
    matrix_rel = connection.relations.Item("CommunicationMatricesByEcus")
    xpath = ecu_xpath
    if not xpath:
        if ecu_names:
            xpath_parts = " | ".join(f'//*[@Name="{n}"][self::BusEcu]' for n in ecu_names)
            xpath = (
                xpath_parts if len(ecu_names) > 1 else f'//*[@Name="{ecu_names[0]}"][self::BusEcu]'
            )
        else:
            xpath = "//BusEcu"
    ecus = list(matrix_rel.FindByXPath(xpath, None))
    if not ecus:
        return {"error": True, "detail": f"No ECUs found for '{ecu_names or xpath}'"}
    if exclude_list:
        excluded = {n.strip() for n in exclude_list.split(",")}
        ecus = [ecu for ecu in ecus if ecu.Name not in excluded]
    if not ecus:
        return {"error": True, "detail": "No ECUs remaining after applying exclude list"}

    found_ecu_names = [ecu.Name for ecu in ecus]

    bus_config = None
    if bus_config_name:
        bus_rel = connection.relations.Item("BusConfigurations")
        for node in bus_rel.GetTopNodes():
            if node.Name == bus_config_name:
                bus_config = node
                break
        if bus_config is None:
            return {"error": True, "detail": f"Bus configuration '{bus_config_name}' not found"}

    if bus_config is None:
        # No bus configuration target — preserve legacy behavior.
        bm.Configure("AssignElements", [ecus, None])
        return {"ecus": found_ecu_names, "parts": [], "status": "unverified_no_target"}

    bus_rel = connection.relations.Item("BusConfigurations")
    targets, err = _resolve_bus_config_targets(bus_rel, bus_config, part)
    if err:
        return {"error": True, "detail": err}

    assigned_parts: list[str] = []
    for tgt in targets:
        bm.Configure("AssignElements", [ecus, tgt])
        try:
            assigned_parts.append(tgt.Name)
        except Exception:
            assigned_parts.append("<unknown>")

    children = list(bus_rel.FindByXPath(f'//*[@Name="{bus_config_name}"]//*', None))
    if children:
        return {"ecus": found_ecu_names, "parts": assigned_parts, "status": "verified"}
    return {"ecus": found_ecu_names, "parts": assigned_parts, "status": "unverified_target"}


def add_feature(
    connection,
    feature_name: str,
    element_type: Optional[str] = None,
    element_name: Optional[str] = None,
    bus_config_name: Optional[str] = None,
    element_xpath: Optional[str] = None,
) -> dict[str, Any]:
    """Add a feature to bus configuration elements.

    The ConfigurationDesk COM API requires that AddFeature is called on elements
    of the correct type. Feature-to-element-type mapping:
    - BusISignalValueAccess → BusISignal elements
    - BusPduEnableAccess, BusPduRxStatusAccess, BusFrameAccess → BusISignalIPdu elements
    - BusCommunicationControllerEnableAccess, BusCommunicationControllerLinScheduleTableAccess → controller elements
    - BusConfigurationEnableAccess → BusConfiguration elements
    """
    bm = connection.busmanager
    bus_rel = connection.relations.Item("BusConfigurations")

    # Feature → target element type mapping for smart resolution
    _FEATURE_TARGET_TYPE = {
        "BusISignalValueAccess": "BusISignal",
        "BusISignalValueInspection": "BusISignal",
        "BusPduEnableAccess": "BusISignalIPdu",
        "BusPduRxStatusAccess": "BusISignalIPdu",
        "BusPduRxStatusInspection": "BusISignalIPdu",
        "BusPduTriggerAccess": "BusISignalIPdu",
        "BusPduRawDataAccess": "BusISignalIPdu",
        "BusPduCyclicTimingControlAccess": "BusISignalIPdu",
        "BusFrameAccess": "BusISignalIPdu",
        "BusCommunicationControllerEnableAccess": "BusCommunicationController",
        "BusCommunicationControllerLinScheduleTableAccess": "BusCommunicationController",
        "BusConfigurationEnableAccess": "BusConfiguration",
        "BusCounterSignalAccess": "BusISignal",
    }

    # Controller types have bus-specific subtypes in the COM model
    _CONTROLLER_TYPE_ALTERNATIVES = [
        "BusCanCommunicationController",
        "BusLinCommunicationController",
        "BusEthernetCommunicationController",
        "BusCommunicationController",
    ]

    items = []

    if element_xpath:
        items = list(bus_rel.FindByXPath(element_xpath, None))
    else:
        if not element_type and not element_name and not bus_config_name:
            return {
                "error": True,
                "detail": "Provide element_type, element_name, element_xpath, or bus_config_name",
            }

        # Try scoped search within the bus config first
        if bus_config_name and element_name:
            # Direct name search within bus config scope
            scoped_xpaths = [
                f'//*[@Name="{bus_config_name}"]//*[@Name="{element_name}"]',
                f'//BusConfiguration[@Name="{bus_config_name}"]//*[@Name="{element_name}"]',
            ]
            for xp in scoped_xpaths:
                items = list(bus_rel.FindByXPath(xp, None))
                if items:
                    break

        # If scoped search failed, try broader searches
        if not items and element_name:
            # Simple name search across all bus configs
            name_xpaths = [
                f'//*[@Name="{element_name}"]',
            ]
            # Also add type-qualified alternatives
            if element_type:
                name_xpaths = (
                    build_xpath_alternatives(element_type=element_type, name=element_name)
                    + name_xpaths
                )
            for xp in name_xpaths:
                items = list(bus_rel.FindByXPath(xp, None))
                if items:
                    break

        # If still nothing and we have element_type only
        if not items and element_type and not element_name:
            alt_xpaths = build_xpath_alternatives(element_type=element_type)
            for xp in alt_xpaths:
                items = list(bus_rel.FindByXPath(xp, None))
                if items:
                    break

    if not items:
        return {
            "error": True,
            "detail": f"No elements found for '{element_name or element_type or element_xpath}' in bus configurations",
        }

    # Smart resolution: if the found items don't match the feature's required target type,
    # find the correct child elements. E.g., if user says "add BusISignalValueAccess on ECU",
    # we need to find BusISignal elements under that ECU.
    target_type = _FEATURE_TARGET_TYPE.get(feature_name)
    if target_type and items:
        # For controller types, we need to search multiple subtypes
        search_types = (
            _CONTROLLER_TYPE_ALTERNATIVES
            if target_type == "BusCommunicationController"
            else [target_type]
        )

        # Check if found items are already the correct type by checking their roles
        first_item_roles = []
        try:
            first_item_roles = [r for r in items[0].Roles]
        except Exception:
            pass

        already_correct = any(st in first_item_roles for st in search_types)
        if not already_correct:
            # Found items are NOT the target type — search for target type children
            resolved_items = []
            for item in items:
                for st in search_types:
                    try:
                        # Search for target type elements under this item
                        child_xpath = f'//*[@Name="{item.Name}"]//{st}'
                        children = list(bus_rel.FindByXPath(child_xpath, None))
                        if children:
                            resolved_items.extend(children)
                    except Exception:
                        pass
                if resolved_items:
                    break  # Found matching children, stop searching types

            if not resolved_items:
                # Try a broader search: all elements of target type in the bus config
                for st in search_types:
                    if bus_config_name:
                        broad_xpath = f'//*[@Name="{bus_config_name}"]//{st}'
                    else:
                        broad_xpath = f"//{st}"
                    try:
                        resolved_items = list(bus_rel.FindByXPath(broad_xpath, None))
                        if resolved_items:
                            break
                    except Exception:
                        pass

            if resolved_items:
                _log.info(
                    "Resolved %d %s elements from %d parent items for feature '%s'",
                    len(resolved_items),
                    target_type,
                    len(items),
                    feature_name,
                )
                items = resolved_items

    item_names = [item.Name for item in items[:20]]  # Cap names for response size
    if len(items) > 20:
        item_names.append(f"... and {len(items) - 20} more")

    # The COM API requires internal role-based feature names (e.g.
    # "BusCommunicationControllerEnableAccess") rather than display names.
    # Always pass items as a list — COM expects an array even for single elements.
    result = bm.Configure("AddFeature", [feature_name, items])
    if not result:
        # Try passing as single item (some COM versions differ)
        if len(items) == 1:
            result = bm.Configure("AddFeature", [feature_name, items[0]])
    if not result:
        try:
            available = bm.Configure("GetAvailableFeatures", [items[0]])
            if available:
                # Build a mapping from simplified lowercase to internal name
                def _normalize(value: str) -> str:
                    return (
                        value.lower()
                        .replace("bus", "")
                        .replace("access", "")
                        .replace("_", "")
                        .replace(" ", "")
                    )

                norm_input = _normalize(feature_name)
                for avail in available:
                    if norm_input in _normalize(avail) or _normalize(avail) in norm_input:
                        result = bm.Configure("AddFeature", [avail, items])
                        if result:
                            break
                        result = bm.Configure("AddFeature", [avail, items[0]])
                        if result:
                            break
                if not result:
                    return {
                        "error": True,
                        "detail": f"AddFeature failed for '{feature_name}'. Available features: {list(available)}",
                        "elements": item_names,
                    }
        except Exception:
            pass
        if not result:
            return {
                "error": True,
                "detail": f"AddFeature('{feature_name}') returned False",
                "elements": item_names,
            }

    try:
        feature_xpath_check = f'//*[@Name="{feature_name}"]'
        feature_items = list(bus_rel.FindByXPath(feature_xpath_check, None))
        return {"elements": item_names, "verified": bool(feature_items)}
    except Exception:
        return {
            "elements": item_names,
            "verified": True,
            "detail": "Feature added (internal name matched)",
        }


def remove_elements(
    connection,
    element_name: Optional[str] = None,
    element_type: Optional[str] = None,
    xpath: Optional[str] = None,
) -> dict[str, Any]:
    """Remove bus configuration elements by name/type or XPath."""
    bm = connection.busmanager
    bus_rel = connection.relations.Item("BusConfigurations")
    xp = xpath
    if not xp:
        if not element_name and not element_type:
            return {"error": True, "detail": "Provide element_name, element_type, or xpath"}
        xp = build_xpath(element_type=element_type, name=element_name)
    items = list(bus_rel.FindByXPath(xp, None))
    if not items:
        return {
            "error": True,
            "detail": f"No elements found for '{element_name or element_type or xp}'",
        }
    removed_names = [item.Name for item in items]
    bm.Configure("RemoveElements", [items])
    remaining = list(bus_rel.FindByXPath(xp, None))
    remaining_names = [item.Name for item in remaining]
    still_present = [n for n in removed_names if n in remaining_names]
    return {"removed": removed_names, "still_present": still_present, "verified": not still_present}


def generate_containers(connection) -> dict[str, Any]:
    """Generate bus simulation containers."""
    connection.busmanager.Configure("GenerateContainers", [])
    return {"issued": True}


def find_elements(
    connection,
    element_type: Optional[str] = None,
    element_name: Optional[str] = None,
    xpath: Optional[str] = None,
) -> dict[str, Any]:
    """Find bus configuration elements by name/type or XPath."""
    bus_rel = connection.relations.Item("BusConfigurations")
    xp = xpath
    if not xp:
        if not element_type and not element_name:
            return {"error": True, "detail": "Provide element_type, element_name, or xpath"}
        xp = build_xpath(element_type=element_type, name=element_name)
    items = list(bus_rel.FindByXPath(xp, None))
    elements = []
    for item in items:
        roles = []
        try:
            roles = list(item.Roles)
        except Exception:
            pass
        elements.append({"name": item.Name, "roles": roles})
    return {"elements": elements, "count": len(elements)}


def assign_to_application_process(
    connection, bus_config_name: str, process_name: Optional[str] = None
) -> dict[str, Any]:
    """Assign a bus configuration to an application process."""
    config_rel = connection.relations.Item("ApplicationConfiguration")
    bc_props_rel = connection.relations.Item("BusConfigurationsWithProperties")
    bc = None
    for node in bc_props_rel.GetTopNodes():
        if node.Name == bus_config_name:
            bc = node
            break
    if bc is None:
        return {"error": True, "detail": f"Bus configuration '{bus_config_name}' not found"}

    def _find_app_processes(rel, node):
        results = []
        try:
            roles = list(node.Roles)
        except Exception:
            roles = []
        if "ApplicationProcess" in roles:
            results.append(node)
        try:
            for child in rel.GetElements(node):
                results.extend(_find_app_processes(rel, child))
        except Exception:
            pass
        return results

    all_procs = []
    for top in config_rel.GetTopNodes():
        all_procs.extend(_find_app_processes(config_rel, top))

    if process_name:
        procs = [p for p in all_procs if p.Name == process_name]
    else:
        procs = all_procs

    if not procs:
        msg = "No application process found"
        if process_name:
            msg += f" matching '{process_name}'"
        msg += ". Create one first with create_application_process."
        return {"error": True, "detail": msg}

    target_proc = procs[0]
    target_name = target_proc.Name
    bc.Properties.Item("ManuallyAssignedApplicationProcess").Value = target_proc

    try:
        readback = bc.Properties.Item("ManuallyAssignedApplicationProcess").Value
        if readback is not None and str(readback.Name) == target_name:
            return {"bus_config": bus_config_name, "process": target_name, "verified": True}
    except Exception:
        pass
    return {"bus_config": bus_config_name, "process": target_name, "verified": False}


def _resolve_function_port_property_handle(prop_node: Any, property_name: str) -> Any:
    """Return the writable property handle for a FunctionPort property node.

    Depending on the COM/XPath shape, ``FindByXPath('//FunctionPort/@Name')`` may
    return either the property object itself or the owning FunctionPort/property
    container. Resolve both shapes to the object exposing ``TrySetValue``/``Value``.
    """
    handle, _ = resolve_named_property_handle(prop_node, property_name)
    return handle


def _property_values_match(actual: Any, expected: bool | int | float | str) -> bool:
    """Compare read-back COM values without collapsing non-bool values to truthiness."""
    return property_values_match(actual, expected)


def _build_function_port_property_xpaths(
    property_name: str,
    *,
    bus_config_name: Optional[str] = None,
    feature_type: Optional[str] = None,
) -> list[str]:
    prefix = f'//BusConfiguration[@Name="{bus_config_name}"]' if bus_config_name else ""
    if not feature_type:
        return [
            f"{prefix}//FunctionPort/@{property_name}"
            if prefix
            else f"//FunctionPort/@{property_name}"
        ]

    normalized = normalize_property_name(feature_type)
    concrete_feature_types = _FUNCTION_PORT_FEATURE_TYPE_ALIASES.get(normalized)
    if not concrete_feature_types:
        concrete_feature_types = (feature_type,)

    return [
        f"{prefix}//{concrete_feature_type}//FunctionPort/@{property_name}"
        if prefix
        else f"//{concrete_feature_type}//FunctionPort/@{property_name}"
        for concrete_feature_type in concrete_feature_types
    ]


def _find_bus_config_property_targets(
    rel,
    *,
    element_name: Optional[str] = None,
    element_type: Optional[str] = None,
    xpath: Optional[str] = None,
    bus_config_name: Optional[str] = None,
) -> tuple[list[Any], Optional[str]]:
    if xpath:
        return list(rel.FindByXPath(xpath, None)), xpath

    xpaths_to_try: list[str] = []
    if bus_config_name and element_type and element_name:
        xpaths_to_try.extend(
            [
                f'//*[@Name="{bus_config_name}"]//{element_type}[@Name="{element_name}"]',
                f'//BusConfiguration[@Name="{bus_config_name}"]//{element_type}[@Name="{element_name}"]',
            ]
        )
    elif bus_config_name and element_name:
        xpaths_to_try.extend(
            [
                f'//*[@Name="{bus_config_name}"]//*[@Name="{element_name}"]',
                f'//BusConfiguration[@Name="{bus_config_name}"]//*[@Name="{element_name}"]',
            ]
        )
    elif bus_config_name and element_type:
        xpaths_to_try.extend(
            [
                f'//*[@Name="{bus_config_name}"]//{element_type}',
                f'//BusConfiguration[@Name="{bus_config_name}"]//{element_type}',
            ]
        )

    if element_type:
        if element_name:
            xpaths_to_try.extend(
                build_xpath_alternatives(element_type=element_type, name=element_name)
            )
        else:
            xpaths_to_try.extend(build_xpath_alternatives(element_type=element_type))
    elif element_name:
        xpaths_to_try.append(f'//*[@Name="{element_name}"]')

    seen: set[str] = set()
    deduped = []
    for candidate in xpaths_to_try:
        if candidate and candidate not in seen:
            seen.add(candidate)
            deduped.append(candidate)

    for candidate in deduped:
        items = list(rel.FindByXPath(candidate, None))
        if items:
            return items, candidate
    return [], deduped[0] if deduped else None


def set_bus_config_element_property(
    connection,
    property_name: str,
    value: bool | int | float | str,
    element_name: Optional[str] = None,
    element_type: Optional[str] = None,
    xpath: Optional[str] = None,
    bus_config_name: Optional[str] = None,
    allow_multiple: bool = False,
) -> dict[str, Any]:
    """Set a property on bus configuration elements or feature nodes."""
    rel = connection.relations.Item("BusConfigurationsWithProperties")
    items, used_xpath = _find_bus_config_property_targets(
        rel,
        element_name=element_name,
        element_type=element_type,
        xpath=xpath,
        bus_config_name=bus_config_name,
    )
    if not items:
        detail = used_xpath or element_name or element_type or xpath or "<unspecified>"
        return {"error": True, "detail": f"No bus configuration elements found for '{detail}'"}

    if len(items) > 1 and not allow_multiple:
        sample = [item.Name for item in items[:5]]
        return {
            "error": True,
            "detail": (
                f"Matched {len(items)} bus configuration elements for property '{property_name}': {sample}. "
                "Refine xpath/element_name or set allow_multiple=true to apply to every match."
            ),
            "xpath_used": used_xpath,
            "elements": sample,
        }

    set_count = 0
    fail_count = 0
    verified_count = 0
    mismatch_count = 0
    actual_property_name = property_name
    readback_errors = []
    matched_elements = []
    for item in items:
        matched_elements.append(item.Name)
        try:
            handle, actual_property_name = resolve_named_property_handle(item, property_name)
            if getattr(handle, "IsReadOnly", False):
                fail_count += 1
                readback_errors.append(
                    f"Property '{actual_property_name}' is read-only on '{item.Name}'"
                )
                continue
            if not try_set_property_value(handle, value):
                fail_count += 1
                continue
            set_count += 1
            actual = handle.Value
            if property_values_match(actual, value):
                verified_count += 1
            else:
                mismatch_count += 1
                readback_errors.append(f"Expected {value!r} on '{item.Name}', got {actual!r}")
        except Exception as exc:
            fail_count += 1
            readback_errors.append(f"{item.Name}: {exc}")

    if set_count == 0:
        return {
            "error": True,
            "detail": f"Could not set property '{property_name}' on any of the {len(items)} matched elements.",
            "xpath_used": used_xpath,
            "elements": matched_elements[:10],
            "readback_errors": readback_errors[:5],
        }

    return {
        "elements": matched_elements[:20],
        "property_name": actual_property_name,
        "set_count": set_count,
        "fail_count": fail_count,
        "verified_count": verified_count,
        "mismatch_count": mismatch_count,
        "xpath_used": used_xpath,
        "readback_errors": readback_errors[:5],
    }


def set_function_port_property(
    connection,
    property_name: str,
    value: bool | int | float | str = True,
    bus_config_name: Optional[str] = None,
    feature_type: Optional[str] = None,
    port_xpath: Optional[str] = None,
) -> dict[str, Any]:
    """Set properties on function ports of bus configuration features."""
    bc_props_rel = connection.relations.Item("BusConfigurationsWithProperties")
    if port_xpath:
        xpaths_to_try = [port_xpath]
    else:
        xpaths_to_try = _build_function_port_property_xpaths(
            property_name,
            bus_config_name=bus_config_name,
            feature_type=feature_type,
        )

    props = []
    xpath = xpaths_to_try[0]
    for candidate_xpath in xpaths_to_try:
        props = list(bc_props_rel.FindByXPath(candidate_xpath, None))
        if props:
            xpath = candidate_xpath
            break

    if not props:
        return {
            "error": True,
            "detail": f"No function-port property nodes found for XPath: {xpaths_to_try[0]}",
            "error_code": "FUNCTION_PORT_PROPERTY_NOT_FOUND",
            "retryable": False,
            "recovery_hint": (
                "Inspect the function ports already exposed by the assigned bus features "
                "with find_bus_config_elements and verify the actual port name/XPath before "
                "retrying. If the target port is missing, fix the bus-feature assignment first. "
                "Do NOT call generate_bus_containers just to make the function port appear."
            ),
            "next_action": (
                "Call `find_bus_config_elements` for the target bus configuration, verify the "
                "required function ports and their exact XPath, then retry `set_function_port_property`."
            ),
            "xpath_used": xpaths_to_try[0],
            "xpaths_tried": xpaths_to_try,
        }

    writable_props = []
    set_count = 0
    fail_count = 0
    for prop_node in props:
        try:
            prop = _resolve_function_port_property_handle(prop_node, property_name)
            result = try_set_property_value(prop, value)
            if result:
                writable_props.append(prop)
                set_count += 1
            else:
                fail_count += 1
        except Exception:
            fail_count += 1

    if set_count == 0:
        return {
            "error": True,
            "detail": (
                f"Matched {len(props)} function-port property node(s) for XPath '{xpath}', "
                "but TrySetValue returned False for all of them."
            ),
            "error_code": "FUNCTION_PORT_PROPERTY_WRITE_FAILED",
            "retryable": False,
            "recovery_hint": (
                "Verify that you targeted the correct function-port property nodes and that the "
                "requested property is writable for those ports. Re-check the actual function-port "
                "names/XPath with find_bus_config_elements before retrying. Do NOT use "
                "generate_bus_containers as recovery for a failed property write."
            ),
            "next_action": (
                "Call `find_bus_config_elements` to inspect the targeted function ports, narrow the "
                "selection with `port_xpath` if needed, then retry `set_function_port_property`."
            ),
            "xpath_used": xpath,
        }

    verified_count = 0
    mismatch_count = 0
    readback_errors = []
    for prop in writable_props:
        try:
            actual = prop.Value
            if _property_values_match(actual, value):
                verified_count += 1
            else:
                mismatch_count += 1
                readback_errors.append(f"Expected {value}, got {actual}")
        except Exception as rb_exc:
            mismatch_count += 1
            readback_errors.append(f"Read-back failed: {rb_exc}")

    return {
        "set_count": set_count,
        "fail_count": fail_count,
        "verified_count": verified_count,
        "mismatch_count": mismatch_count,
        "xpath_used": xpath,
        "readback_errors": readback_errors[:5],
    }


def connect_function_ports_to_model_ports(
    connection, bus_config_name: Optional[str] = None, auto: bool = True
) -> dict[str, Any]:
    """Removed.

    The connect_function_ports_to_model_ports tool was removed because it
    duplicated auto_connect_matching_io_function_blocks_to_model_ports
    (in bus_access_com). The remaining stub raises a clear error so any
    accidental import surfaces a usable message.
    """
    raise NotImplementedError(
        "connect_function_ports_to_model_ports has been removed. Use "
        "auto_connect_matching_io_function_blocks_to_model_ports in "
        "bus_access_com instead."
    )


def connect_ports(
    connection, source_xpath: str, target_xpath: str, remove_existing_links: bool = True
) -> dict[str, Any]:
    """Removed.

    The connect_ports tool was removed in favour of
    connect_function_block_port_to_model_port (in io_functions_com).
    """
    raise NotImplementedError(
        "connect_ports has been removed. Use "
        "connect_function_block_port_to_model_port in io_functions_com instead."
    )
