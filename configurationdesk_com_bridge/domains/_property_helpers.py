from __future__ import annotations

from typing import Any, Iterator


def normalize_property_name(value: str) -> str:
    if not value:
        return ""
    return "".join(ch.lower() for ch in value if ch.isalnum())


def iter_properties(properties: Any) -> Iterator[Any]:
    count = getattr(properties, "Count", 0)
    for index in range(count):
        yield properties.Item(index)


def resolve_named_property_handle(node: Any, property_name: str) -> tuple[Any, str]:
    normalized = normalize_property_name(property_name)

    if hasattr(node, "TrySetValue") and hasattr(node, "Value"):
        actual_name = getattr(node, "Name", property_name) or property_name
        if not normalized or normalize_property_name(actual_name) == normalized:
            return node, actual_name

    properties = getattr(node, "Properties", None)
    if properties is None:
        raise AttributeError(f"Node for '{property_name}' has no Properties collection")

    for accessor in (
        lambda: properties[property_name],
        lambda: properties.Item(property_name),
    ):
        try:
            handle = accessor()
            actual_name = getattr(handle, "Name", property_name) or property_name
            return handle, actual_name
        except Exception:
            pass

    for handle in iter_properties(properties):
        actual_name = getattr(handle, "Name", "") or ""
        if normalize_property_name(actual_name) == normalized:
            return handle, actual_name

    raise KeyError(
        f"Property '{property_name}' not found on node '{getattr(node, 'Name', '<unknown>')}'"
    )


def property_values_match(actual: Any, expected: bool | int | float | str) -> bool:
    if isinstance(expected, bool):
        if isinstance(actual, bool):
            return actual is expected
        if isinstance(actual, (int, float)):
            return actual in (0, 1) and bool(actual) is expected
        return False

    if isinstance(expected, int):
        if isinstance(actual, bool):
            return expected in (0, 1) and actual is bool(expected)
        return not isinstance(actual, bool) and actual == expected

    if isinstance(expected, float):
        if isinstance(actual, bool):
            return expected in (0.0, 1.0) and actual is bool(expected)
        return not isinstance(actual, bool) and actual == expected

    return actual == expected


def try_set_property_value(handle: Any, value: bool | int | float | str) -> bool:
    try:
        if hasattr(handle, "TrySetValue") and handle.TrySetValue(value):
            return True
    except Exception:
        pass

    try:
        handle.Value = value
        return True
    except Exception:
        return False
