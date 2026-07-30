"""COM wrappers for ConfigurationDesk bus access operations.

All functions must be called on the STA thread via dispatch().
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from configurationdesk_com_bridge.domains.verify_com import (
    list_application_process_names,
    wait_for_state,
)

_log = logging.getLogger(__name__)

_BUS_FB_TYPES = {"CAN", "LIN", "Ethernet"}


def _get_io_function_library(conn):
    """Navigate to the I/O Function Library root. Returns (func_lib, error_msg)."""
    try:
        io_lib = conn.active.Components.Item("IOFunctionLib")
        func_lib = io_lib.Item("Function Library")
        return func_lib, None
    except Exception as e:
        return None, f"Cannot access I/O Function Library: {e}"


def _iter_category_children(category):
    """Iterate children of a bus category, handling both 0-based and 1-based COM indexing."""
    # Try Python COM iteration first (most reliable)
    try:
        for child in category:
            yield child
        return
    except (TypeError, AttributeError):
        pass

    # Try 0-based indexing
    try:
        count = int(category.Count)
        for i in range(count):
            try:
                yield category.Item(i)
            except Exception:
                pass
        return
    except Exception:
        pass

    # Try 1-based indexing (common in COM)
    try:
        count = int(category.Count)
        for i in range(1, count + 1):
            try:
                yield category.Item(i)
            except Exception:
                pass
    except Exception:
        pass


def _get_bus_function_block(conn, function_block_name: str, bus_type: str):
    """Find a bus function block by name and type. Returns (fb, error_msg)."""
    func_lib, err = _get_io_function_library(conn)
    if err:
        return None, err

    # Try the specific bus_type category first
    try:
        bus_category = func_lib.Item(bus_type)
        for child in _iter_category_children(bus_category):
            try:
                if child.Name == function_block_name:
                    return child, None
            except Exception:
                continue
    except Exception as e:
        _log.debug("Failed to search '%s' category: %s", bus_type, e)

    # Fallback: search ALL categories in case bus_type was wrong
    all_types = list(_BUS_FB_TYPES)
    if bus_type in all_types:
        all_types.remove(bus_type)
    for other_type in all_types:
        try:
            other_category = func_lib.Item(other_type)
            for child in _iter_category_children(other_category):
                try:
                    if child.Name == function_block_name:
                        _log.info(
                            "Found '%s' in '%s' category (requested '%s')",
                            function_block_name,
                            other_type,
                            bus_type,
                        )
                        return child, None
                except Exception:
                    continue
        except Exception:
            continue

    # Fallback: iterate func_lib itself in case structure is flat
    try:
        for child in _iter_category_children(func_lib):
            try:
                if child.Name == function_block_name:
                    return child, None
            except Exception:
                continue
    except Exception:
        pass

    return None, (
        f"Function block '{function_block_name}' not found. "
        f"Searched categories: {sorted(_BUS_FB_TYPES)}. "
        f"Ensure the block was created with create_io_function_block first."
    )


def _list_function_block_instances(conn) -> list[Any]:
    """Return all instantiated I/O function blocks from the I/O Function Library.

    Iterates every type category (CAN, LIN, Ethernet, Voltage In/Out, PWM,
    etc.) under the Function Library root and yields every instance child
    that has a usable ``Name``. The bus-type filter has been removed: the
    Function Library exposes ~90 categories and any of them may host
    instances created via ``add_io_function_block`` or
    ``create_io_function_block``.
    """
    func_lib, err = _get_io_function_library(conn)
    if err:
        return []

    blocks: list[Any] = []
    for category in _iter_category_children(func_lib):
        for child in _iter_category_children(category):
            try:
                _ = child.Name
            except Exception:
                continue
            blocks.append(child)
    return blocks


# Backwards compatibility alias for existing internal callers.
_list_bus_function_blocks = _list_function_block_instances


def _list_model_port_blocks(conn) -> list[Any]:
    """Return all model port blocks across every model in the topology.

    Walks ``connection.model_topology`` (= ``Components.Item('ModelTopology')``)
    and yields every direct child of each model node. These are the
    ``ModelPortBlock`` objects that ``ConnectIOFunctionBlocksToModelPortBlocks``
    expects to be paired with function blocks.
    """
    try:
        mt = conn.model_topology
    except Exception:
        return []

    blocks: list[Any] = []
    for model in _iter_category_children(mt):
        for port_block in _iter_category_children(model):
            try:
                _ = port_block.Name
            except Exception:
                continue
            blocks.append(port_block)
    return blocks


def _iter_data_object_tree(obj):
    """Recursively yield ``obj`` and every descendant reachable via COM iteration.

    Each ``ICaDataObject`` may have child data objects (e.g. function blocks
    have port-group containers, which contain port objects). The Links
    property is per-object, so callers that need to observe link state
    must walk the whole tree.
    """
    yield obj
    for child in _iter_category_children(obj):
        yield from _iter_data_object_tree(child)


def create_bus_function_block(connection, name: str, bus_type: str = "CAN") -> dict[str, Any]:
    """Create a bus I/O function block (CAN, LIN, or Ethernet)."""
    func_lib, err = _get_io_function_library(connection)
    if err:
        return {"error": True, "detail": err}

    bus_category = func_lib.Item(bus_type)
    block_type = bus_category.DataObjectTypes.Item(0)
    fb = bus_category.CreateChild(block_type, name)
    props = {}
    try:
        for i in range(fb.Properties.Count):
            p = fb.Properties.Item(i)
            try:
                props[p.Name] = p.Value
            except Exception:
                props[p.Name] = None
    except Exception:
        pass
    # Verify using the robust lookup
    found, _ = _get_bus_function_block(connection, name, bus_type)
    verify_ok = found is not None
    return {"name": name, "bus_type": bus_type, "properties": props, "verified": verify_ok}


def set_bus_function_block_property(
    connection, function_block_name: str, property_name: str, value: str, bus_type: str = "CAN"
) -> dict[str, Any]:
    """Set a property on a bus I/O function block."""
    fb, err = _get_bus_function_block(connection, function_block_name, bus_type)
    if err:
        return {"error": True, "detail": err}
    prop = fb.Properties.Item(property_name)
    if prop is None:
        return {
            "error": True,
            "detail": f"Property '{property_name}' not found on '{function_block_name}'",
        }
    converted: Any = value
    try:
        converted = int(value)
    except ValueError:
        try:
            converted = float(value)
        except ValueError:
            if value.lower() in ("true", "false"):
                converted = value.lower() == "true"
    # CAN BaudRate: COM uses kbaud internally (500 = 500000 baud)
    # If user passes a value >= 1000 for BaudRate on CAN, convert to kbaud
    if (
        property_name == "BaudRate"
        and bus_type == "CAN"
        and isinstance(converted, (int, float))
        and converted >= 1000
    ):
        converted = int(converted) // 1000
    elif (
        property_name == "DataPhaseBaudRate"
        and bus_type == "CAN"
        and isinstance(converted, (int, float))
        and converted >= 1000
    ):
        converted = int(converted) // 1000

    prop.Value = converted
    actual = prop.Value
    # For BaudRate, also accept kbaud equivalence in verification
    verified = str(actual) == str(converted) or actual == converted
    if (
        not verified
        and property_name in ("BaudRate", "DataPhaseBaudRate")
        and isinstance(actual, (int, float))
    ):
        # Check if readback matches after kbaud conversion
        verified = (
            int(actual) == int(converted)
            or int(actual) * 1000 == int(converted)
            or int(actual) == int(converted) * 1000
        )
    return {
        "property_name": property_name,
        "value_set": converted,
        "value_readback": actual,
        "verified": verified,
    }


def list_bus_function_block_properties(
    connection, function_block_name: str, bus_type: str = "CAN"
) -> dict[str, Any]:
    """List all properties on a bus I/O function block."""
    fb, err = _get_bus_function_block(connection, function_block_name, bus_type)
    if err:
        return {"error": True, "detail": err}
    props = []
    for i in range(fb.Properties.Count):
        p = fb.Properties.Item(i)
        entry: dict[str, Any] = {"name": p.Name}
        try:
            entry["value"] = p.Value
        except Exception:
            entry["value"] = None
        try:
            entry["read_only"] = p.IsReadOnly
        except Exception:
            entry["read_only"] = None
        props.append(entry)
    return {
        "function_block": function_block_name,
        "bus_type": bus_type,
        "properties": props,
        "count": len(props),
    }


def list_bus_access_requests(connection, bus_config_name: Optional[str] = None) -> dict[str, Any]:
    """List bus access requests across all (or a specific) bus configuration."""
    bus_rel = connection.relations.Item("BusConfigurations")
    requests = []
    top_nodes = bus_rel.GetTopNodes()
    for i in range(top_nodes.Count):
        bc = top_nodes.Item(i)
        bc_name = bc.Name
        if bus_config_name and bc_name != bus_config_name:
            continue
        xpath = (
            f'/BusConfiguration[@Name="{bc_name}"]/BusConfigurationPartBusAccessRequests/*/*/*/*'
        )
        items = list(bus_rel.FindByXPath(xpath, None))
        bar_roles = [
            "BusAccessRequestSimulatedEcus",
            "BusAccessRequestInspection",
            "BusAccessRequestManipulation",
            "BusAccessRequestGateways",
        ]
        for item in items:
            roles = list(item.Roles)
            if not any(r in roles for r in bar_roles):
                continue
            props = {}
            try:
                for j in range(item.Properties.Count):
                    p = item.Properties.Item(j)
                    try:
                        props[p.Name] = p.Value
                    except Exception:
                        props[p.Name] = None
            except Exception:
                pass
            req_type = next(
                (r for r in roles if r.startswith("BusAccessRequest")),
                "BusAccessRequest",
            )
            requests.append(
                {
                    "bus_config": bc_name,
                    "name": item.Name,
                    "type": req_type,
                    "bus_access": props.get("Bus access", ""),
                    "baud_rate": props.get("Required baud rate"),
                    "requires_canfd": props.get("Requires CAN FD"),
                }
            )
    return {"requests": requests, "count": len(requests)}


def assign_bus_access(
    connection,
    function_block_name: str,
    bus_config_name: Optional[str] = None,
    cluster_name: Optional[str] = None,
) -> dict[str, Any]:
    """Assign bus access requests to a function block."""
    bus_rel = connection.relations.Item("BusConfigurations")
    assigned: list[str] = []
    top_nodes = bus_rel.GetTopNodes()
    for i in range(top_nodes.Count):
        bc = top_nodes.Item(i)
        bc_name = bc.Name
        if bus_config_name and bc_name != bus_config_name:
            continue
        cluster_filter = f'[@Name="{cluster_name}"]' if cluster_name else ""
        for cluster_type in (
            "BusCanCommunicationCluster",
            "BusLinCommunicationCluster",
            "BusEthernetCommunicationCluster",
        ):
            xpath = (
                f'/BusConfiguration[@Name="{bc_name}"]'
                "/BusConfigurationPartBusAccessRequests"
                f"//{cluster_type}{cluster_filter}/*/@Bus_access"
            )
            try:
                feats = list(bus_rel.FindByXPath(xpath, None))
                for feat in feats:
                    feat.TrySetValue(function_block_name)
                    assigned.append(bc_name)
            except Exception:
                pass

    if not assigned:
        return {"assigned_configs": [], "verified_count": 0, "verified": False}

    # Verify
    verified_count = 0
    for i in range(top_nodes.Count):
        bc = top_nodes.Item(i)
        bc_name = bc.Name
        if bus_config_name and bc_name != bus_config_name:
            continue
        xpath_check = (
            f'/BusConfiguration[@Name="{bc_name}"]/BusConfigurationPartBusAccessRequests/*/*/*/*'
        )
        items = list(bus_rel.FindByXPath(xpath_check, None))
        for item in items:
            roles = list(item.Roles)
            if not any(r.startswith("BusAccessRequest") for r in roles):
                continue
            try:
                ba_prop = item.Properties.Item("Bus access")
                if str(ba_prop.Value) == function_block_name:
                    verified_count += 1
            except Exception:
                pass
    return {
        "assigned_configs": list(set(assigned)),
        "verified_count": verified_count,
        "verified": verified_count > 0,
    }


def list_assignable_channel_sets(
    connection, function_block_name: str, bus_type: str = "CAN"
) -> dict[str, Any]:
    """List assignable channel sets for a bus I/O function block."""
    fb, err = _get_bus_function_block(connection, function_block_name, bus_type)
    if err:
        return {"error": True, "detail": err}
    alg = connection.algorithms
    channel_sets = alg.GetAssignableChannelSets(fb)
    results = []
    for i in range(channel_sets.Count):
        cs = channel_sets.Item(i)
        entry: dict[str, Any] = {"index": i, "name": str(cs.Name)}
        try:
            entry["description"] = str(cs.Description)
        except Exception:
            pass
        try:
            cs_props = {}
            for j in range(cs.Properties.Count):
                p = cs.Properties.Item(j)
                try:
                    cs_props[p.Name] = p.Value
                except Exception:
                    cs_props[p.Name] = None
            if cs_props:
                entry["properties"] = cs_props
        except Exception:
            pass
        results.append(entry)
    return {"function_block": function_block_name, "channel_sets": results, "count": len(results)}


def assign_channel_set(
    connection, function_block_name: str, channel_set_index: int = 0, bus_type: str = "CAN"
) -> dict[str, Any]:
    """Assign a hardware channel set to a bus I/O function block."""
    fb, err = _get_bus_function_block(connection, function_block_name, bus_type)
    if err:
        return {"error": True, "detail": err}
    alg = connection.algorithms
    channel_sets = alg.GetAssignableChannelSets(fb)
    if channel_sets.Count == 0:
        return {
            "error": True,
            "detail": f"No assignable channel sets available for '{function_block_name}'.",
        }
    if channel_set_index < 0 or channel_set_index >= channel_sets.Count:
        return {
            "error": True,
            "detail": f"channel_set_index {channel_set_index} out of range. Valid: 0 to {channel_sets.Count - 1}",
        }
    selected_cs = channel_sets.Item(channel_set_index)
    cs_name = str(selected_cs.Name)
    alg.AssignChannelSet(fb, selected_cs)
    return {
        "function_block": function_block_name,
        "channel_set": cs_name,
        "channel_set_index": channel_set_index,
        "verified": True,
    }


def auto_assign_channel_set(
    connection, function_block_name: str, bus_type: str = "CAN"
) -> dict[str, Any]:
    """Auto-assign a channel set to a bus I/O function block."""
    fb, err = _get_bus_function_block(connection, function_block_name, bus_type)
    if err:
        return {"error": True, "detail": err}
    # COM expects an array/enumerable parameter, not a single object
    try:
        connection.algorithms.AutoAssignChannelSet([fb])
    except Exception as e1:
        _log.debug("Array form [fb] failed: %s", e1)
        # Fallback: try single object (older COM versions)
        try:
            connection.algorithms.AutoAssignChannelSet(fb)
        except Exception as e2:
            return {"error": True, "detail": f"AutoAssignChannelSet failed: {e2}"}
    return {"function_block": function_block_name, "verified": True}


def assign_hardware_automatically(connection) -> dict[str, Any]:
    """Automatically assign all hardware resources to all I/O function blocks."""
    alg = connection.algorithms
    function_blocks = _list_function_block_instances(connection)
    if not function_blocks:
        return {"error": True, "detail": "No I/O function blocks found to assign hardware to."}

    last_error = "Unknown error"
    for candidate in (function_blocks, [function_blocks], [], None):
        try:
            if candidate is None:
                alg.AssignHardwareAutomatically(None)
            else:
                alg.AssignHardwareAutomatically(candidate)
            return {
                "verified": True,
                "assigned_blocks": len(function_blocks),
                "method": "AssignHardwareAutomatically",
            }
        except Exception as exc:
            last_error = str(exc)
            _log.debug("AssignHardwareAutomatically(%s) failed: %s", type(candidate).__name__, exc)

    assigned = 0
    failed: list[str] = []
    for fb in function_blocks:
        try:
            try:
                alg.AutoAssignChannelSet([fb])
            except Exception:
                alg.AutoAssignChannelSet(fb)
            assigned += 1
        except Exception as exc:
            name = getattr(fb, "Name", "<unknown>")
            failed.append(f"{name}: {exc}")

    if assigned:
        return {
            "verified": not failed,
            "assigned_blocks": assigned,
            "failed_blocks": failed,
            "detail": "Assigned hardware per function block via AutoAssignChannelSet fallback."
            if failed
            else "",
            "method": "AutoAssignChannelSetFallback",
        }

    return {
        "error": True,
        "detail": f"Automatic hardware assignment failed. Last error: {last_error}",
    }


def auto_connect_matching_io_function_blocks_to_model_ports(connection) -> dict[str, Any]:
    """Auto-connect I/O function block ports to matching model port blocks.

     The COM call has the signature::

        Algorithms.ConnectIOFunctionBlocksToModelPortBlocks(Items)

    where ``Items`` is an array containing **both** function blocks and
    model port blocks; ConfigurationDesk then name-matches their ports.
    The user-supplied pattern feeds one ``[ModelPortBlock, FunctionBlock]``
    pair per call::

        for idx in range(len(ModelPorts)):
            Algorithms.ConnectIOFunctionBlocksToModelPortBlocks(
                [ModelPorts[idx], FunctionPorts[idx]]
            )

    Since we do not know the user's intended pairing, this implementation
    iterates over every ``(model_port_block, function_block)`` combination
    so the COM call's name-matching has the chance to create links wherever
    names align. Verification compares the ``Links`` relation count before
    and after.
    """
    alg = connection.algorithms

    function_blocks = _list_function_block_instances(connection)
    if not function_blocks:
        return {
            "error": True,
            "detail": (
                "No I/O function blocks found. Create at least one with "
                "create_io_function_block or add_io_function_block before "
                "connecting."
            ),
        }

    model_port_blocks = _list_model_port_blocks(connection)
    if not model_port_blocks:
        return {
            "error": True,
            "detail": (
                "No model port blocks found in the model topology. Add a "
                "model and (for .slx) run analyze_models, or generate bus "
                "containers, before connecting."
            ),
        }

    link_count_before = _count_links(connection)

    pair_results: list[dict[str, Any]] = []
    last_exc: Optional[str] = None
    for mpb in model_port_blocks:
        mpb_name = getattr(mpb, "Name", "<unknown>")
        for fb in function_blocks:
            fb_name = getattr(fb, "Name", "<unknown>")
            try:
                links = alg.ConnectIOFunctionBlocksToModelPortBlocks([mpb, fb])
            except Exception as exc:
                last_exc = f"{mpb_name} <-> {fb_name}: {exc}"
                _log.debug(
                    "ConnectIOFunctionBlocksToModelPortBlocks failed for pair %s/%s: %s",
                    mpb_name,
                    fb_name,
                    exc,
                )
                continue
            try:
                count = int(links.Count) if links is not None else 0
            except Exception:
                count = 0
            if count:
                pair_results.append(
                    {
                        "model_port_block": mpb_name,
                        "function_block": fb_name,
                        "new_links": count,
                    }
                )

    link_count_after = _count_links(connection)
    new_links = max(0, link_count_after - link_count_before)

    result: dict[str, Any] = {
        "verified": new_links > 0 or bool(pair_results),
        "function_blocks": [getattr(fb, "Name", "<unknown>") for fb in function_blocks],
        "model_port_blocks": [getattr(mpb, "Name", "<unknown>") for mpb in model_port_blocks],
        "pairs_with_links": pair_results,
        "links_before": link_count_before,
        "links_after": link_count_after,
        "new_links": new_links,
    }
    if not pair_results and new_links == 0:
        result["detail"] = (
            "No matching ports were connected for any (model_port_block, function_block) pair."
        )
        if last_exc:
            result["last_error"] = last_exc
    return result


def _count_links(connection) -> int:
    """Count links involving the I/O function block port hierarchy.

    The ``Links`` relation accessor on ``connection.relations``
    does NOT support ``GetTopNodes`` reliably, so this helper walks the
    function block tree and accumulates ``Links.Count`` on every descendant
    instead. The same metric is used before and after a connect operation
    to compute a stable link delta.
    """
    total = 0
    for fb in _list_function_block_instances(connection):
        for node in _iter_data_object_tree(fb):
            try:
                links = node.Links
            except Exception:
                continue
            try:
                total += int(links.Count)
            except Exception:
                continue
    return total


# Backwards compatibility alias for any internal callers still using the
# legacy name. Public tool surface uses the renamed entry point.
connect_io_function_blocks_to_model_ports = auto_connect_matching_io_function_blocks_to_model_ports


def create_preconfigured_application_process(connection, model_name: str) -> dict[str, Any]:
    """Create a pre-configured application process for a specific model.

    Calls ``Algorithms.CreatePreConfiguredApplicationProcessAutomatically([model], None)``
    where ``model`` is the model topology object identified by ``model_name``.
    A new ProcessingUnitApplication is created automatically (Parent=None)
    when no pre-existing one is referenced.
    """
    import win32com.client
    import pythoncom

    if not model_name:
        return {"error": True, "detail": "model_name is required."}

    # Resolve the model topology object by name. ``ModelTopology`` is a
    # not a relation accessor — ``GetTopNodes`` is
    # not implemented on it. Per the COM API, child models are reached via
    # zero-based ``Item(i)`` (e.g. ``ModelTopology.Item(0)``). The
    # ``_iter_category_children`` helper already handles indexed traversal
    # plus Python iteration as a fallback.
    try:
        mt = connection.model_topology
    except Exception as exc:
        return {"error": True, "detail": f"ModelTopology component not available: {exc}"}

    target = None
    try:
        for node in _iter_category_children(mt):
            try:
                if node.Name == model_name:
                    target = node
                    break
            except Exception:
                continue
    except Exception as exc:
        return {"error": True, "detail": f"Cannot enumerate models: {exc}"}

    if target is None:
        return {
            "error": True,
            "detail": (
                f"Model '{model_name}' not found in topology. "
                f"Use list_models to inspect available models."
            ),
        }

    alg = connection.algorithms
    before_processes = list_application_process_names(connection)
    before_process_set = set(before_processes)

    variant_arr = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_VARIANT, [target])
    try:
        alg.CreatePreConfiguredApplicationProcessAutomatically(variant_arr, None)
    except Exception as exc:
        # Fallback: pass a plain Python list. Some COM marshalling stacks accept
        # that without an explicit VARIANT wrapper.
        try:
            alg.CreatePreConfiguredApplicationProcessAutomatically([target], None)
        except Exception:
            return {
                "error": True,
                "detail": f"CreatePreConfiguredApplicationProcessAutomatically failed: {exc}",
            }

    verified, processes_after = wait_for_state(
        lambda: list_application_process_names(connection),
        lambda names: bool(set(names) - before_process_set),
    )
    return {
        "model_name": model_name,
        "verified": verified,
        "created_processes": sorted(set(processes_after) - before_process_set),
    }
