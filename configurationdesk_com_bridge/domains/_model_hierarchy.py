"""Hierarchy helpers for ConfigurationDesk model topology nodes.

The model topology is a tree: a model contains subsystems and model port
blocks, subsystems contain further subsystems and model port blocks, and
model port blocks contain model ports, e.g.
``ModelTopology.Item('DoorControlModel').Item('Controller').Item('Left Door')``.
Model port blocks with the same name can therefore exist at several
hierarchy levels (``demosmd_io/Wavetable`` and ``demosmd_io/Subsystem/Wavetable``)
and only the hierarchy path identifies them uniquely.

All functions that touch COM objects must be called on the STA thread.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from configurationdesk_com_bridge.domains._property_helpers import (
    iter_properties,
    normalize_property_name,
)

PATH_SEPARATOR = "/"

# Property names (normalized) that identify a node kind in the model topology.
_PORT_PROPERTIES = frozenset({"porttype", "signalid", "datatype", "datawidth"})
_BLOCK_PROPERTIES = frozenset({"blockid", "sourcename", "path"})

_PORT = "port"
_BLOCK = "block"
_GROUP = "group"


@dataclass(frozen=True)
class ModelPortBlockRef:
    """A model port block together with its hierarchy path in the model."""

    name: str
    path: str
    parent_path: str
    block: Any


def _children(node: Any) -> list[Any]:
    try:
        return list(node)
    except Exception:
        pass
    try:
        return [node.Item(index) for index in range(int(node.Count))]
    except Exception:
        return []


def _name(node: Any) -> str | None:
    try:
        return node.Name
    except Exception:
        return None


def _property_names(node: Any) -> set[str]:
    properties = getattr(node, "Properties", None)
    if properties is None:
        return set()
    names: set[str] = set()
    try:
        for handle in iter_properties(properties):
            names.add(normalize_property_name(getattr(handle, "Name", "") or ""))
    except Exception:
        return set()
    return names


def _node_kind(node: Any) -> str:
    """Classify a model topology node as model port, model port block, or group.

    Real ConfigurationDesk nodes are classified by their property set: model
    ports expose ``PortType``/``SignalID``, model port blocks expose
    ``BlockID``/``Source name``/``Path``, and subsystems expose only ``Name``.
    Nodes without a property collection fall back to their tree shape.
    """
    names = _property_names(node)
    if names & _PORT_PROPERTIES:
        return _PORT
    if names & _BLOCK_PROPERTIES:
        return _BLOCK
    children = _children(node)
    if not children:
        return _PORT if not names else _GROUP
    if all(_node_kind(child) == _PORT for child in children):
        return _BLOCK
    return _GROUP


def collect_model_port_blocks(model_block: Any, model_name: str) -> list[ModelPortBlockRef]:
    """Return every model port block of a model, recursing into subsystems."""
    refs: list[ModelPortBlockRef] = []

    def walk(node: Any, parent_path: str) -> None:
        for child in _children(node):
            name = _name(child)
            if name is None:
                continue
            kind = _node_kind(child)
            path = f"{parent_path}{PATH_SEPARATOR}{name}"
            if kind == _BLOCK:
                refs.append(ModelPortBlockRef(name, path, parent_path, child))
            elif kind == _GROUP:
                walk(child, path)

    walk(model_block, model_name)
    return refs


def normalize_block_path(value: str) -> str:
    return value.replace("\\", PATH_SEPARATOR).strip(PATH_SEPARATOR)


def match_model_port_blocks(
    refs: list[ModelPortBlockRef], model_name: str, spec: str
) -> list[ModelPortBlockRef]:
    """Return the model port blocks addressed by *spec*.

    *spec* is either a bare block name, which matches blocks with that name at
    every hierarchy level, or a hierarchy path such as
    ``demosmd_io/Subsystem/Wavetable`` or the model-relative
    ``Subsystem/Wavetable``. A root-level block is addressed unambiguously by
    prefixing the model name, e.g. ``demosmd_io/Wavetable``.
    """
    normalized = normalize_block_path(spec)
    if PATH_SEPARATOR in normalized:
        candidates = {normalized, f"{model_name}{PATH_SEPARATOR}{normalized}"}
        exact = [ref for ref in refs if ref.path in candidates]
        if exact:
            return exact
    return [ref for ref in refs if ref.name == spec]


def distinct_parent_paths(refs: list[ModelPortBlockRef]) -> list[str]:
    return list(dict.fromkeys(ref.parent_path for ref in refs))


def distinct_paths(refs: list[ModelPortBlockRef]) -> list[str]:
    return list(dict.fromkeys(ref.path for ref in refs))


def names_at_multiple_levels(refs: list[ModelPortBlockRef]) -> dict[str, list[str]]:
    """Map each block name that occurs at more than one hierarchy level to its paths."""
    by_name: dict[str, list[ModelPortBlockRef]] = {}
    for ref in refs:
        by_name.setdefault(ref.name, []).append(ref)
    return {
        name: distinct_paths(group)
        for name, group in by_name.items()
        if len(distinct_parent_paths(group)) > 1
    }


def block_identifier(ref: ModelPortBlockRef, ambiguous: dict[str, list[str]]) -> str:
    """Return the shortest identifier that addresses *ref* without hierarchy ambiguity."""
    return ref.path if ref.name in ambiguous else ref.name


def ambiguous_hierarchy_error(
    model_name: str, port_block_name: str, matches: list[ModelPortBlockRef]
) -> dict[str, Any]:
    """Error payload for a block name that exists at several hierarchy levels."""
    candidates = distinct_paths(matches)
    return {
        "error": True,
        "reason": "ambiguous_model_port_block_hierarchy",
        "candidates": candidates,
        "detail": (
            f"Model '{model_name}' has model port blocks named '{port_block_name}' at "
            f"{len(distinct_parent_paths(matches))} hierarchy levels: {candidates}. "
            "The name alone does not identify which one is meant."
        ),
    }
