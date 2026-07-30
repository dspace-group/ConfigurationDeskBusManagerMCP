"""COM wrappers for ConfigurationDesk communication matrix operations.

All functions must be called on the STA thread via dispatch().
"""

from __future__ import annotations

import os
import logging
from typing import Any, Optional

from configurationdesk_com_bridge.domains._property_helpers import (
    property_values_match,
    resolve_named_property_handle,
    try_set_property_value,
)
from configurationdesk_com_bridge.domains.verify_com import (
    build_xpath,
    build_xpath_alternatives,
    get_top_node_names,
    wait_for_state,
)

_log = logging.getLogger(__name__)


def add_communication_matrix(connection, path: str) -> dict[str, Any]:
    """Add an ARXML, DBC, or LDF communication matrix file to the project."""
    abs_path = os.path.abspath(path)
    before_clusters = get_top_node_names("CommunicationMatricesByClusters", connection)
    before_ecus = get_top_node_names("CommunicationMatricesByEcus", connection)
    connection.busmanager.Configure("AddCommunicationMatrix", [abs_path])
    verified, (after_clusters, after_ecus) = wait_for_state(
        lambda: (
            get_top_node_names("CommunicationMatricesByClusters", connection),
            get_top_node_names("CommunicationMatricesByEcus", connection),
        ),
        lambda state: bool(
            (set(state[0]) - set(before_clusters)) or (set(state[1]) - set(before_ecus))
        ),
    )
    new_clusters = sorted(set(after_clusters) - set(before_clusters))
    new_ecus = sorted(set(after_ecus) - set(before_ecus))
    return {
        "path": abs_path,
        "new_clusters": new_clusters,
        "new_ecus": new_ecus,
        "verified": verified,
    }


def remove_communication_matrix(
    connection, name: Optional[str] = None, xpath: Optional[str] = None, force: bool = False
) -> dict[str, Any]:
    """Remove a communication matrix from the project by name or XPath."""
    bm = connection.busmanager
    rel = connection.relations.Item("CommunicationMatricesByClusters")
    xp = xpath
    items = []
    if not xp:
        if not name:
            return {"error": True, "detail": "Provide a matrix name or xpath"}
        for relation_name in ("CommunicationMatricesByClusters", "CommunicationMatricesByEcus"):
            try:
                relation = connection.relations.Item(relation_name)
            except Exception:
                continue
            for node in relation.GetTopNodes():
                if node.Name == name:
                    items = [node]
                    rel = relation
                    break
            if items:
                break
    if not items:
        if not xp:
            xp = build_xpath(name=name)
        items = list(rel.FindByXPath(xp, None))
        if not items:
            try:
                rel = connection.relations.Item("CommunicationMatricesByEcus")
                items = list(rel.FindByXPath(xp, None))
            except Exception:
                items = []
    if not items:
        return {"error": True, "detail": f"No matrix elements found for '{name or xp}'"}
    removed_names = [item.Name for item in items]
    for item in items:
        bm.Configure("RemoveCommunicationMatrix", [item, force])
    remaining = list(rel.FindByXPath(xp, None))
    still_present = [item.Name for item in remaining]
    return {"removed": removed_names, "still_present": still_present, "verified": not still_present}


def list_matrices(connection) -> dict[str, Any]:
    """List all communication matrices by clusters and ECUs views."""
    matrices: dict[str, list[str]] = {"clusters": [], "ecus": []}
    clusters_rel = connection.relations.Item("CommunicationMatricesByClusters")
    for node in clusters_rel.GetTopNodes():
        matrices["clusters"].append(node.Name)
    ecus_rel = connection.relations.Item("CommunicationMatricesByEcus")
    for node in ecus_rel.GetTopNodes():
        matrices["ecus"].append(node.Name)
    return {"matrices": matrices}


def find_matrix_elements(
    connection,
    element_type: Optional[str] = None,
    element_name: Optional[str] = None,
    xpath: Optional[str] = None,
    view: str = "clusters",
) -> dict[str, Any]:
    """Find communication matrix elements by name/type or XPath.

    element_type accepts user-friendly names: 'signal', 'frame', 'pdu', 'ecu'.
    These are mapped to COM internal type names (BusISignal, BusFrame, etc.).
    """
    rel_name = (
        "CommunicationMatricesByClusters" if view == "clusters" else "CommunicationMatricesByEcus"
    )
    rel = connection.relations.Item(rel_name)

    if xpath:
        items = list(rel.FindByXPath(xpath, None))
        elements = []
        for item in items:
            entry = {"name": item.Name}
            try:
                entry["roles"] = list(item.Roles)
            except Exception:
                pass
            elements.append(entry)
        return {"elements": elements, "count": len(elements)}

    if not element_type and not element_name:
        return {"error": True, "detail": "Provide element_type, element_name, or xpath"}

    # Try multiple XPath alternatives (maps 'signal' → 'BusISignal' etc.)
    xpaths_to_try = build_xpath_alternatives(element_type=element_type, name=element_name)
    if not xpaths_to_try:
        xpaths_to_try = [build_xpath(element_type=element_type, name=element_name)]

    elements = []
    used_xpath = None
    for xp in xpaths_to_try:
        try:
            items = list(rel.FindByXPath(xp, None))
            if items:
                used_xpath = xp
                for item in items:
                    entry = {"name": item.Name}
                    try:
                        entry["roles"] = list(item.Roles)
                    except Exception:
                        pass
                    elements.append(entry)
                break
        except Exception:
            continue

    # If cluster view returned nothing, try ECU view as fallback
    if not elements and view == "clusters":
        alt_rel = connection.relations.Item("CommunicationMatricesByEcus")
        for xp in xpaths_to_try:
            try:
                items = list(alt_rel.FindByXPath(xp, None))
                if items:
                    used_xpath = xp
                    for item in items:
                        entry = {"name": item.Name}
                        try:
                            entry["roles"] = list(item.Roles)
                        except Exception:
                            pass
                        elements.append(entry)
                    break
            except Exception:
                continue

    # Last resort: if element_type is "ecu" and still nothing, try traversing top nodes
    if not elements and element_type and element_type.lower() == "ecu":
        try:
            ecu_rel = connection.relations.Item("CommunicationMatricesByEcus")
            for node in ecu_rel.GetTopNodes():
                try:
                    # Top nodes are usually matrix packages — children are ECUs
                    children_xpath = f'//*[@Name="{node.Name}"]//*'
                    children = list(ecu_rel.FindByXPath(children_xpath, None))
                    for child in children:
                        entry = {"name": child.Name}
                        try:
                            entry["roles"] = list(child.Roles)
                        except Exception:
                            pass
                        elements.append(entry)
                except Exception:
                    # Just add the top node itself
                    elements.append({"name": node.Name})
        except Exception:
            pass

    return {"elements": elements, "count": len(elements), "xpath_used": used_xpath}


def _matrix_relation_order(view: str) -> list[str]:
    if view == "ecus":
        return ["CommunicationMatricesByEcus", "CommunicationMatricesByClusters"]
    return ["CommunicationMatricesByClusters", "CommunicationMatricesByEcus"]


def _find_matrix_property_targets(
    connection,
    *,
    element_type: Optional[str] = None,
    element_name: Optional[str] = None,
    xpath: Optional[str] = None,
    view: str = "clusters",
) -> tuple[list[Any], Optional[str], Optional[str]]:
    xpaths_to_try: list[str] = []
    if xpath:
        xpaths_to_try.append(xpath)
    elif element_type:
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

    for relation_name in _matrix_relation_order(view):
        rel = connection.relations.Item(relation_name)
        for candidate in deduped:
            items = list(rel.FindByXPath(candidate, None))
            if items:
                return items, candidate, relation_name
    return [], deduped[0] if deduped else None, None


def set_matrix_element_property(
    connection,
    property_name: str,
    value: bool | int | float | str,
    element_name: Optional[str] = None,
    element_type: Optional[str] = None,
    xpath: Optional[str] = None,
    view: str = "clusters",
    allow_multiple: bool = False,
) -> dict[str, Any]:
    """Set a property on communication-matrix elements."""
    items, used_xpath, relation_name = _find_matrix_property_targets(
        connection,
        element_name=element_name,
        element_type=element_type,
        xpath=xpath,
        view=view,
    )
    if not items:
        detail = used_xpath or element_name or element_type or xpath or "<unspecified>"
        return {"error": True, "detail": f"No matrix elements found for '{detail}'"}

    if len(items) > 1 and not allow_multiple:
        sample = [item.Name for item in items[:5]]
        return {
            "error": True,
            "detail": (
                f"Matched {len(items)} matrix elements for property '{property_name}': {sample}. "
                "Refine xpath/element_name or set allow_multiple=true to apply to every match."
            ),
            "xpath_used": used_xpath,
            "relation": relation_name,
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
            "detail": f"Could not set property '{property_name}' on any of the {len(items)} matched matrix elements.",
            "xpath_used": used_xpath,
            "relation": relation_name,
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
        "relation": relation_name,
        "readback_errors": readback_errors[:5],
    }
