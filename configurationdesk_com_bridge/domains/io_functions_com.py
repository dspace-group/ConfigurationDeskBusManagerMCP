"""COM wrappers for ConfigurationDesk I/O Functions Library operations.

These wrappers operate on the generic I/O Functions Library (analog/digital
signals such as 'Voltage Out', 'Voltage In', 'PWM Out', 'Digital In') —
distinct from the CAN/LIN/Ethernet bus function blocks handled in
``bus_access_com``.

All functions must be called on the STA thread via dispatch().
"""

from __future__ import annotations

import logging
from typing import Any

from configurationdesk_com_bridge.domains._model_hierarchy import (
    ambiguous_hierarchy_error,
    collect_model_port_blocks,
    distinct_parent_paths,
    distinct_paths,
    match_model_port_blocks,
)
from configurationdesk_com_bridge.domains.verify_com import wait_for_state

_log = logging.getLogger(__name__)


def _get_io_func_lib_root(conn):
    """Return the I/O Functions Library root container, or (None, error_msg)."""
    try:
        io_lib = conn.active.Components.Item("IOFunctionLib")
        root = io_lib.Item(0)
        return root, None
    except Exception as e:
        return None, f"Cannot access I/O Functions Library root: {e}"


def _iter_children(container):
    """Iterate children of a COM container, handling Python iteration and
    both 0-based and 1-based ``Item`` indexing.
    """
    # Try Python COM iteration first (most reliable)
    try:
        for child in container:
            yield child
        return
    except (TypeError, AttributeError):
        pass

    # Try 0-based indexing
    try:
        count = int(container.Count)
        for i in range(count):
            try:
                yield container.Item(i)
            except Exception:
                pass
        return
    except Exception:
        pass

    # Try 1-based indexing (common in COM)
    try:
        count = int(container.Count)
        for i in range(1, count + 1):
            try:
                yield container.Item(i)
            except Exception:
                pass
    except Exception:
        pass


def _dump_properties(obj) -> dict[str, Any]:
    """Best-effort dump of an object's ``Properties`` collection into a dict."""
    props: dict[str, Any] = {}
    try:
        for i in range(obj.Properties.Count):
            p = obj.Properties.Item(i)
            try:
                props[p.Name] = p.Value
            except Exception:
                props[p.Name] = None
    except Exception:
        pass
    return props


def add_io_function_block(connection, function_type_name: str, block_name: str) -> dict[str, Any]:
    """Add an I/O function block instance of the given type to the signal chain.

    Mirrors the user-supplied sample::

        IOFuncLib = Application.ActiveApplication.Components.IOFunctionLib.Item(0)
        VoltageOut = IOFuncLib.Item("Voltage Out").DataObjectTypes.Item(0)
        VoltageBlock = IOFuncLib.CreateChild(VoltageOut, "Voltage1")
    """
    root, err = _get_io_func_lib_root(connection)
    if err:
        return {"error": True, "detail": err}
    before_names = []
    for child in _iter_children(root):
        try:
            before_names.append(child.Name)
        except Exception:
            pass

    # Resolve the function type by name (e.g. "Voltage Out").
    try:
        type_category = root.Item(function_type_name)
    except Exception as e:
        return {
            "error": True,
            "detail": (
                f"I/O function type '{function_type_name}' not found in "
                f"the I/O Functions Library: {e}"
            ),
        }

    # Get the first DataObjectType for this function type.
    try:
        data_object_type = type_category.DataObjectTypes.Item(0)
    except Exception as e:
        return {
            "error": True,
            "detail": (
                f"I/O function type '{function_type_name}' has no usable DataObjectType: {e}"
            ),
        }

    # Create the instance in the signal chain.
    try:
        fb = root.CreateChild(data_object_type, block_name)
    except Exception as e:
        return {
            "error": True,
            "detail": (
                f"Failed to create I/O function block '{block_name}' of type "
                f"'{function_type_name}': {e}"
            ),
        }

    props = _dump_properties(fb)

    verified, all_names = wait_for_state(
        lambda: [child.Name for child in _iter_children(root) if hasattr(child, "Name")],
        lambda names: block_name in names or len(names) > len(before_names),
    )

    return {
        "name": block_name,
        "function_type": function_type_name,
        "properties": props,
        "all_blocks": all_names,
        "verified": verified,
    }


def list_io_function_block_types(connection) -> dict[str, Any]:
    """List the available I/O function block type names from the library.

    Enumerates the children of ``Components.Item("IOFunctionLib").Item(0)``
    and returns each child's ``Name``. These names are the valid values
    to pass as ``function_type_name`` to ``add_io_function_block``.
    """
    root, err = _get_io_func_lib_root(connection)
    if err:
        return {"error": True, "detail": err}

    types: list[dict[str, Any]] = []
    for child in _iter_children(root):
        entry: dict[str, Any] = {}
        try:
            entry["name"] = child.Name
        except Exception:
            continue
        types.append(entry)

    return {"types": types, "count": len(types)}


def _find_child_by_name(container, name: str):
    """Return the child of ``container`` whose ``.Name`` matches ``name``.

    Tries ``container.Item(name)`` first (fast path) and falls back to
    iterating children and matching ``.Name`` exactly. Returns None if not
    found.
    """
    try:
        item = container.Item(name)
        # ``Item`` may succeed but return the wrong sibling collection on some
        # COM containers, so confirm by Name when possible.
        try:
            if item is not None and item.Name == name:
                return item
        except Exception:
            return item
    except Exception:
        pass
    for child in _iter_children(container):
        try:
            if child.Name == name:
                return child
        except Exception:
            continue
    return None


def _find_function_block_instance(root, function_block_name: str):
    """Locate a function block instance by name under the IOFunctionLib root.

    Instances live under their type container, e.g.
    ``IOFuncLib.Item("Voltage Out").Item("MyVoltage")``. Since the caller
    only supplies the instance name, iterate each type category and look
    for a child whose ``.Name`` matches ``function_block_name``.
    Returns ``(fb, type_name)`` or ``(None, None)`` if not found.
    """
    for type_category in _iter_children(root):
        try:
            type_name = type_category.Name
        except Exception:
            type_name = None
        candidate = _find_child_by_name(type_category, function_block_name)
        if candidate is not None:
            return candidate, type_name
    return None, None


def _find_function_block_port(fb, port_name: str):
    """Locate a port on a function block instance by name.

    Per the user-supplied sample, ports are nested one level deep under
    a port-group container, e.g.
    ``VoltageBlock.Item("Voltage Out").Item("Voltage")``. Try a direct
    lookup first (in case the port is at the top level on some block
    types), then fall back to scanning each child container.
    """
    direct = _find_child_by_name(fb, port_name)
    if direct is not None:
        try:
            # If this is the actual port, it usually exposes ConnectableObjects
            # or is itself connectable; either way, treat as a valid match
            # unless it is a port-group container that has its own children
            # with the same name we'll find below.
            return direct
        except Exception:
            return direct

    for port_group in _iter_children(fb):
        nested = _find_child_by_name(port_group, port_name)
        if nested is not None:
            return nested
    return None


def _safe_name(obj) -> str | None:
    try:
        return obj.Name
    except Exception:
        return None


def _resolve_model_port(
    model_block,
    model_name: str,
    model_port_block_name: str,
    model_port_name: str | None,
) -> tuple[Any, str | None, dict[str, Any] | None]:
    """Resolve the model port to connect.

    Returns ``(port, port_block_path, error_dict)``. A model port block name
    that exists at several hierarchy levels is rejected as ambiguous, even if
    ``model_port_name`` is given, because the caller must decide which block
    is meant.
    """
    refs = collect_model_port_blocks(model_block, model_name)
    matches = match_model_port_blocks(refs, model_name, model_port_block_name)
    if not matches:
        return (
            None,
            None,
            {
                "error": True,
                "available_port_blocks": distinct_paths(refs),
                "detail": (
                    f"Model port block '{model_port_block_name}' not found on model '{model_name}'."
                ),
            },
        )
    if len(distinct_parent_paths(matches)) > 1:
        return None, None, ambiguous_hierarchy_error(model_name, model_port_block_name, matches)

    port_block_path = matches[0].path
    blocks = [ref.block for ref in matches]

    if model_port_name is None:
        if len(blocks) == 1:
            # Preserve the documented behavior: first model port of the block.
            try:
                return blocks[0].Item(0), port_block_path, None
            except Exception as e:
                return (
                    None,
                    None,
                    {
                        "error": True,
                        "detail": (
                            f"Cannot access port on model port block '{port_block_path}': {e}"
                        ),
                    },
                )
        available_ports = [
            name
            for block in blocks
            for name in (_safe_name(port) for port in _iter_children(block))
            if name
        ]
        return (
            None,
            None,
            {
                "error": True,
                "reason": "ambiguous_model_port_block",
                "available_model_ports": available_ports,
                "detail": (
                    f"Model '{model_name}' has {len(blocks)} model port blocks named "
                    f"'{model_port_block_name}' at '{port_block_path}'. Specify "
                    "model_port_name to choose one of its model ports: "
                    f"{available_ports}."
                ),
            },
        )

    port_matches = []
    available: list[str] = []
    for block in blocks:
        for port in _iter_children(block):
            name = _safe_name(port)
            if name:
                available.append(name)
            if name == model_port_name:
                port_matches.append(port)

    if not port_matches:
        return (
            None,
            None,
            {
                "error": True,
                "reason": "model_port_not_found",
                "available_model_ports": available,
                "detail": (
                    f"Model port '{model_port_name}' not found in model port block "
                    f"'{port_block_path}'. Available model ports: {available}."
                ),
            },
        )
    if len(port_matches) > 1:
        return (
            None,
            None,
            {
                "error": True,
                "reason": "ambiguous_model_port",
                "available_model_ports": available,
                "detail": (
                    f"Model port '{model_port_name}' exists {len(port_matches)} times in "
                    f"model port blocks at '{port_block_path}'."
                ),
            },
        )
    return port_matches[0], port_block_path, None


def connect_function_block_port_to_model_port(
    connection,
    function_block_name: str,
    function_block_port_name: str,
    model_name: str,
    model_port_block_name: str,
    model_port_name: str | None = None,
) -> dict[str, Any]:
    """Connect a single function block port to a single model port.

    The model port block is resolved from ``model_port_block_name``: a bare
    name is searched at every hierarchy level of the model (including
    subsystems) and a hierarchy path such as ``Model/Subsystem/Block``
    addresses one level exactly. A bare name found at several hierarchy levels
    is rejected as ambiguous. When ``model_port_name`` is given, that named
    port is searched in every matching model port block of that level;
    otherwise the first port of the (unique) model port block is used.

    Mirrors the sample::

        ModelTopology = Application.ActiveApplication.Components.ModelTopology
        ModelPortBlock = ModelTopology.Item('SineWaves').Item('Sine_t')
        ModelPort = ModelPortBlock.Item(0)

        IOFuncLib = Application.ActiveApplication.Components.IOFunctionLib.Item(0)
        VoltageOut = IOFuncLib.Item("Voltage Out")
        VoltageBlock = VoltageOut.Item('MyVoltage')
        VoltageBlockPort = VoltageBlock.Item('Voltage Out').Item('Voltage')

        Application.ActiveApplication.ConnectObjects(VoltageBlockPort, ModelPort)
    """
    # ── Resolve the function block instance under IOFunctionLib root ────────
    root, err = _get_io_func_lib_root(connection)
    if err:
        return {"error": True, "detail": err}

    fb, _fb_type_name = _find_function_block_instance(root, function_block_name)
    if fb is None:
        return {
            "error": True,
            "detail": (
                f"Function block '{function_block_name}' not found in the "
                "I/O Functions Library. Add it first with "
                "`add_io_function_block`."
            ),
        }

    # ── Resolve the named port on the function block (nested port group) ────
    fb_port = _find_function_block_port(fb, function_block_port_name)
    if fb_port is None:
        return {
            "error": True,
            "detail": (
                f"Port '{function_block_port_name}' not found on function "
                f"block '{function_block_name}'."
            ),
        }

    # ── Resolve the model port block in ModelTopology ───────────────────────
    try:
        mt = connection.model_topology
    except Exception as e:
        return {
            "error": True,
            "detail": f"Cannot access ModelTopology component: {e}",
        }

    model_block = _find_child_by_name(mt, model_name)
    if model_block is None:
        return {
            "error": True,
            "detail": (
                f"Model '{model_name}' not found in ModelTopology. "
                "Ensure the model has been added with `add_model`."
            ),
        }

    model_port, port_block_path, port_err = _resolve_model_port(
        model_block, model_name, model_port_block_name, model_port_name
    )
    if port_err is not None:
        return port_err
    resolved_port_name = _safe_name(model_port)

    # ── Issue the connection ────────────────────────────────────────────────
    try:
        connection.active.ConnectObjects(fb_port, model_port)
    except Exception as e:
        return {
            "error": True,
            "reason": "connect_failed",
            "detail": (
                f"ConnectObjects failed for "
                f"'{function_block_name}.{function_block_port_name}' -> "
                f"'{port_block_path}/{resolved_port_name}': {e}"
            ),
        }

    # ── Verify by inspecting the function block port's Links collection ─────
    verified = False
    try:
        links = fb_port.Links
        if links is not None and int(links.Count) > 0:
            verified = True
    except Exception:
        pass

    return {
        "function_block_name": function_block_name,
        "function_block_port_name": function_block_port_name,
        "model_name": model_name,
        "model_port_block_name": model_port_block_name,
        "model_port_block_path": port_block_path,
        "model_port_name": resolved_port_name,
        "verified": verified,
    }
