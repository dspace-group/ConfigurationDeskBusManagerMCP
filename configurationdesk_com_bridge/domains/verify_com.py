"""Post-call verification helpers and XPath builder.

Every mutating domain function should verify the outcome after a COM call
rather than assuming "no exception == success".

All functions run on the STA thread — they access COM objects directly.
"""

from __future__ import annotations

import os
import logging
import time
from typing import Callable, Iterable, List, Optional, Tuple, TypeVar

_log = logging.getLogger(__name__)

_DEFAULT_OBSERVE_TIMEOUT_S = 10.0
_DEFAULT_POLL_INTERVAL_S = 0.1

_StateT = TypeVar("_StateT")


# ── XPath builder ──────────────────────────────────────────────────────────

# Map user-friendly element type names to COM internal type names.
# The COM tree uses BusXxx prefixed names for bus topology elements.
_ELEMENT_TYPE_MAP: dict[str, list[str]] = {
    "signal": ["BusISignal", "BusSignal", "ISignal", "BusISignalGroup"],
    "frame": ["BusFrame", "BusCanFrame", "BusLinFrame", "BusEthernetFrame"],
    "pdu": ["BusPdu", "BusIPdu", "BusTxIPdu", "BusRxIPdu", "IPdu", "BusGeneralPurposePdu"],
    "ecu": [
        "BusNetworkNode",
        "BusEcu",
        "BusEcuInstance",
        "EcuInstance",
        "BusCommunicationConnector",
    ],
    "cluster": [
        "BusCommunicationCluster",
        "BusCanCommunicationCluster",
        "BusLinCommunicationCluster",
        "BusEthernetCommunicationCluster",
    ],
    "controller": [
        "BusCommunicationController",
        "CommunicationController",
        "BusCanCommunicationController",
        "BusLinCommunicationController",
    ],
    "network_node": ["BusNetworkNode", "BusCommunicationConnector"],
    "gateway": ["BusGateway", "Gateway"],
    "channel": ["BusPhysicalChannel", "BusCanPhysicalChannel", "BusLinPhysicalChannel"],
}


def build_xpath(
    element_type: Optional[str] = None,
    name: Optional[str] = None,
    *,
    parent_type: Optional[str] = None,
    parent_name: Optional[str] = None,
) -> str:
    """Build an XPath expression from user-friendly parameters.

    Maps user-friendly type names (signal, frame, pdu, ecu) to COM internal
    type names (BusISignal, BusFrame, BusPdu, BusEcu).
    """
    if not element_type and not name:
        raise ValueError("At least one of element_type or name must be provided")

    # Resolve the COM internal type name(s)
    resolved_type = element_type
    if element_type and element_type.lower() in _ELEMENT_TYPE_MAP:
        # Use the first (most common) mapping
        resolved_type = _ELEMENT_TYPE_MAP[element_type.lower()][0]

    if name and resolved_type:
        return f'//*[@Name="{name}"][self::{resolved_type}]'
    if name:
        return f'//*[@Name="{name}"]'
    return f"//{resolved_type}"


def build_xpath_alternatives(
    element_type: Optional[str] = None,
    name: Optional[str] = None,
) -> list[str]:
    """Build multiple XPath alternatives for robust element lookup.

    Returns a list of XPaths to try, from most specific to broadest.
    """
    xpaths = []

    if element_type and element_type.lower() in _ELEMENT_TYPE_MAP:
        type_variants = _ELEMENT_TYPE_MAP[element_type.lower()]
        if name:
            for t in type_variants:
                xpaths.append(f'//*[@Name="{name}"][self::{t}]')
            xpaths.append(f'//*[@Name="{name}"]')
        else:
            for t in type_variants:
                xpaths.append(f"//{t}")
            # Broadest: match anything with a role containing the type
            xpaths.append("//*")
    elif element_type:
        # Not in our map — try as-is and with Bus prefix
        if name:
            xpaths.append(f'//*[@Name="{name}"][self::{element_type}]')
            xpaths.append(f'//*[@Name="{name}"][self::Bus{element_type}]')
            xpaths.append(f'//*[@Name="{name}"]')
        else:
            xpaths.append(f"//{element_type}")
            xpaths.append(f"//Bus{element_type}")
    elif name:
        xpaths.append(f'//*[@Name="{name}"]')

    return xpaths


# ── Relation helpers ───────────────────────────────────────────────────────


def get_top_node_names(relation_name: str, connection) -> List[str]:
    rel = connection.relations.Item(relation_name)
    return [node.Name for node in rel.GetTopNodes()]


def _iter_relation_nodes(rel, parent=None) -> Iterable:
    try:
        nodes = rel.GetTopNodes() if parent is None else rel.GetElements(parent)
    except Exception:
        return []

    collected = []
    for node in nodes:
        collected.append(node)
        collected.extend(_iter_relation_nodes(rel, node))
    return collected


def _iter_com_items(collection) -> Iterable:
    """Yield items from COM-style collections that may be iterable or indexed."""
    try:
        for item in collection:
            yield item
        return
    except (TypeError, AttributeError):
        pass

    try:
        count = int(collection.Count)
    except Exception:
        return

    for start in (0, 1):
        yielded = False
        for index in range(start, count + start):
            try:
                item = collection.Item(index)
            except Exception:
                continue
            yielded = True
            yield item
        if yielded:
            return


def _read_string_name(node) -> Optional[str]:
    try:
        name = node.Name
    except Exception:
        return None
    if isinstance(name, str) and name.strip():
        return name
    return None


def _read_roles(node) -> list[str]:
    try:
        roles = list(node.Roles)
    except Exception:
        return []
    return [role for role in roles if isinstance(role, str)]


def count_top_nodes(relation_name: str, connection) -> int:
    rel = connection.relations.Item(relation_name)
    return sum(1 for _ in rel.GetTopNodes())


def xpath_result_count(relation_name: str, xpath: str, connection) -> int:
    rel = connection.relations.Item(relation_name)
    return sum(1 for _ in rel.FindByXPath(xpath, None))


def _pump_waiting_messages() -> None:
    try:
        import pythoncom  # noqa: PLC0415

        pythoncom.PumpWaitingMessages()
    except Exception:
        pass


def wait_for_state(
    read_state: Callable[[], _StateT],
    is_ready: Callable[[_StateT], bool],
    *,
    timeout_s: float = _DEFAULT_OBSERVE_TIMEOUT_S,
    poll_interval_s: float = _DEFAULT_POLL_INTERVAL_S,
) -> Tuple[bool, _StateT]:
    """Poll COM-observable state until *is_ready* returns True or timeout elapses.

    This runs on the STA thread. Between polls it pumps pending COM messages so
    asynchronous ConfigurationDesk work can progress before the next readback.
    """
    state = read_state()
    deadline = time.perf_counter() + timeout_s

    while not is_ready(state):
        if time.perf_counter() >= deadline:
            return False, state
        _pump_waiting_messages()
        time.sleep(poll_interval_s)
        _pump_waiting_messages()
        state = read_state()

    return True, state


def wait_for_new_names(
    read_names: Callable[[], List[str]],
    before_names: List[str],
    *,
    timeout_s: float = _DEFAULT_OBSERVE_TIMEOUT_S,
    poll_interval_s: float = _DEFAULT_POLL_INTERVAL_S,
) -> Tuple[bool, List[str], List[str]]:
    """Wait until *read_names* exposes at least one name not in *before_names*."""
    before_set = set(before_names)
    verified, current_names = wait_for_state(
        read_names,
        lambda names: bool(set(names) - before_set),
        timeout_s=timeout_s,
        poll_interval_s=poll_interval_s,
    )
    added = sorted(set(current_names) - before_set)
    return verified, added, current_names


def list_application_process_names(connection) -> List[str]:
    try:
        rel = connection.relations.Item("ApplicationConfiguration")
    except Exception:
        return []

    names: list[str] = []
    for node in _iter_relation_nodes(rel):
        try:
            roles = list(node.Roles)
        except Exception:
            roles = []
        if "ApplicationProcess" in roles:
            names.append(node.Name)
    return names


# ── Verification primitives ───────────────────────────────────────────────


def verify_exists(relation_name: str, item_name: str, connection) -> Tuple[bool, str]:
    try:
        names = get_top_node_names(relation_name, connection)
        if item_name in names:
            return True, f"'{item_name}' found in {relation_name}"
        return False, f"'{item_name}' NOT found in {relation_name}. Present: {names}"
    except Exception as exc:
        return False, f"Verification query failed: {exc}"


def verify_not_exists(relation_name: str, item_name: str, connection) -> Tuple[bool, str]:
    try:
        names = get_top_node_names(relation_name, connection)
        if item_name not in names:
            return True, f"'{item_name}' confirmed absent from {relation_name}"
        return False, f"'{item_name}' still present in {relation_name}"
    except Exception as exc:
        return False, f"Verification query failed: {exc}"


def verify_count_changed(
    relation_name: str,
    connection,
    old_count: int,
    direction: str = "increased",
) -> Tuple[bool, str]:
    try:
        new_count = count_top_nodes(relation_name, connection)
        if direction == "increased" and new_count > old_count:
            return True, f"Count increased from {old_count} to {new_count}"
        if direction == "decreased" and new_count < old_count:
            return True, f"Count decreased from {old_count} to {new_count}"
        return False, (f"Count did not {direction}: was {old_count}, now {new_count}")
    except Exception as exc:
        return False, f"Verification query failed: {exc}"


def verify_contains(com_collection, name: str) -> Tuple[bool, str]:
    try:
        if com_collection.Contains(name):
            return True, f"'{name}' found in collection"
        return False, f"'{name}' NOT found in collection"
    except Exception as exc:
        return False, f"Verification query failed: {exc}"


def verify_not_contains(com_collection, name: str) -> Tuple[bool, str]:
    try:
        if not com_collection.Contains(name):
            return True, f"'{name}' confirmed absent from collection"
        return False, f"'{name}' still present in collection"
    except Exception as exc:
        return False, f"Verification query failed: {exc}"


def verify_active_project(connection, expected_name: str) -> Tuple[bool, str]:
    try:
        actual = connection.app.ActiveProject.Name
        if actual == expected_name:
            return True, f"Active project is '{expected_name}'"
        return False, f"Active project is '{actual}', expected '{expected_name}'"
    except Exception as exc:
        return False, f"Verification query failed: {exc}"


def verify_active_application(connection, expected_name: str) -> Tuple[bool, str]:
    try:
        # Try simple path first (works on most COM interface versions)
        try:
            actual = connection.app.ActiveApplication.Name
        except Exception:
            # Legacy path: some versions nest Application under ActiveApplication
            actual = connection.app.ActiveApplication.Application.Name
        if actual == expected_name:
            return True, f"Active application is '{expected_name}'"
        return False, f"Active application is '{actual}', expected '{expected_name}'"
    except Exception as exc:
        return False, f"Verification query failed: {exc}"


def verify_no_active_project(connection) -> Tuple[bool, str]:
    try:
        proj = connection.app.ActiveProject
        if proj is None:
            return True, "No active project"
        try:
            _ = proj.Name
            return False, f"Project '{proj.Name}' is still active"
        except Exception:
            return True, "No active project (COM object invalid)"
    except Exception:
        return True, "No active project"


def verify_file_exists(path: str) -> Tuple[bool, str]:
    if os.path.isfile(path):
        return True, f"File exists: {path}"
    return False, f"File NOT found: {path}"


# ── Model topology helpers ─────────────────────────────────────────────────


def list_model_names(connection) -> List[str]:
    models: list[str] = []

    try:
        mt = connection.model_topology
    except Exception:
        mt = None

    if mt is not None:
        for model in _iter_com_items(mt):
            name = _read_string_name(model)
            if name:
                models.append(name)

    if not models:
        try:
            rel = connection.relations.Item("ApplicationConfiguration")
        except Exception:
            rel = None

        if rel is not None:
            for top in _iter_com_items(rel.GetTopNodes()):
                for elem in _iter_com_items(rel.GetElements(top)):
                    name = _read_string_name(elem)
                    if not name:
                        continue
                    roles = _read_roles(elem)
                    if any("Model" in role for role in roles):
                        models.append(name)

    return list(dict.fromkeys(models))


def count_config_nodes(connection) -> int:
    try:
        rel = connection.relations.Item("ApplicationConfiguration")
        count = 0
        for top in rel.GetTopNodes():
            count += 1
            try:
                for _ in rel.GetElements(top):
                    count += 1
            except Exception:
                pass
        return count
    except Exception:
        return 0
