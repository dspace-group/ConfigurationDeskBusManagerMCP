# -*- coding: utf-8 -*-
"""Common bus element and matrix property names, aliases, and type hints."""

from __future__ import annotations

from sources.models.property_values import PropertyValue


class _Prop:
    __slots__ = (
        "canonical",
        "description",
        "extra_aliases",
        "value_type",
        "example",
        "scopes",
    )

    def __init__(
        self,
        canonical: str,
        description: str,
        *,
        extra_aliases: tuple[str, ...] = (),
        value_type: str = "int",
        example: object = None,
        scopes: tuple[str, ...] = ("bus_config", "matrix"),
    ) -> None:
        self.canonical = canonical
        self.description = description
        self.extra_aliases = extra_aliases
        self.value_type = value_type
        self.example = example
        self.scopes = scopes


COMMON_BUS_ELEMENT_PROPERTIES: tuple[_Prop, ...] = (
    _Prop(
        canonical="Countdown start value",
        description=(
            "Temporary manipulation countdown applied to the selected feature "
            "or feature switch. Common in manipulation features such as Frame "
            "Length and Suspend Frame Transmission."
        ),
        extra_aliases=("Countdown Start Value",),
        value_type="int",
        example=15,
        scopes=("bus_config",),
    ),
    _Prop(
        canonical="Feature switch",
        description=(
            "Selects the initially active manipulation feature for the "
            "related ISignal feature switch node."
        ),
        extra_aliases=("Feature Switch",),
        value_type="int",
        example=1,
        scopes=("bus_config",),
    ),
    _Prop(
        canonical="Enable",
        description=(
            "Feature enable mode. ConfigurationDesk exposes this as an integer "
            "code on several manipulation feature nodes."
        ),
        extra_aliases=("Enable mode",),
        value_type="int",
        example=1,
        scopes=("bus_config",),
    ),
    _Prop(
        canonical="Length",
        description=(
            "Payload or signal length depending on the target element. For "
            "matrix PDUs/ISignals it edits the communication matrix; for Frame "
            "Length manipulation features it sets the manipulated frame length."
        ),
        extra_aliases=("Length - Frame Length", "Frame Length"),
        value_type="int",
        example=1,
    ),
    _Prop(
        canonical="Padding value",
        description="Padding byte pattern used by Frame Length manipulation.",
        extra_aliases=("Padding Value",),
        value_type="int",
        example=0,
        scopes=("bus_config",),
    ),
    _Prop(
        canonical="Unused bit pattern",
        description="Unused-bit fill pattern on communication-matrix PDUs.",
        extra_aliases=("Unused Bit Pattern",),
        value_type="int",
        example=0,
        scopes=("matrix",),
    ),
    _Prop(
        canonical="Initial value",
        description=(
            "Initial value on communication-matrix signal elements. Type may "
            "depend on the signal data type, so numeric and textual values are "
            "passed through."
        ),
        extra_aliases=("InitialValue",),
        value_type="scalar",
        example=1,
        scopes=("matrix",),
    ),
    _Prop(
        canonical="Overwrite value",
        description=(
            "Manipulated ISignal overwrite value. The type depends on the signal data type."
        ),
        extra_aliases=("Overwrite Value", "Overwrite Value - ISignal Overwrite Value"),
        value_type="scalar",
        example=255,
        scopes=("bus_config",),
    ),
    _Prop(
        canonical="Offset value",
        description=("Manipulated ISignal offset value. The type depends on the signal data type."),
        extra_aliases=("Offset Value", "Offset Value - ISignal Offset Value"),
        value_type="scalar",
        example=3,
        scopes=("bus_config",),
    ),
    _Prop(
        canonical="Recalculate SecOC information",
        description="Whether SecOC data is recalculated after manipulation.",
        extra_aliases=("Recalculate SecOC Information",),
        value_type="bool",
        example=False,
        scopes=("bus_config",),
    ),
    _Prop(
        canonical="Recalculate end-to-end protection",
        description="Whether E2E protection is recalculated after manipulation.",
        extra_aliases=("Recalculate End-To-End Protection",),
        value_type="bool",
        example=False,
        scopes=("bus_config",),
    ),
)


def _normalize(value: str) -> str:
    if not value:
        return ""
    return "".join(ch.lower() for ch in value if ch.isalnum())


def _build_alias_map() -> dict[str, str]:
    table: dict[str, str] = {}
    for prop in COMMON_BUS_ELEMENT_PROPERTIES:
        for raw in (prop.canonical, *prop.extra_aliases):
            key = _normalize(raw)
            if key:
                table.setdefault(key, prop.canonical)
    return table


_ALIAS_MAP: dict[str, str] = _build_alias_map()
_PROPERTIES_BY_CANONICAL: dict[str, _Prop] = {
    prop.canonical: prop for prop in COMMON_BUS_ELEMENT_PROPERTIES
}


def resolve_property_name(property_name: str) -> tuple[str, str | None]:
    if not property_name:
        return property_name, None
    canonical = _ALIAS_MAP.get(_normalize(property_name))
    if canonical and canonical != property_name:
        return canonical, property_name
    return property_name, None


def validate_property_value(
    canonical_name: str,
    value: PropertyValue,
    *,
    scope: str | None = None,
) -> tuple[bool, str | None]:
    prop = _PROPERTIES_BY_CANONICAL.get(canonical_name)
    if prop is None:
        return True, None
    if scope and scope not in prop.scopes:
        return True, None

    expected = prop.value_type
    is_bool = isinstance(value, bool)

    if expected == "bool":
        if not is_bool:
            return False, (
                f"Property '{canonical_name}' expects bool (true or false), got "
                f"{type(value).__name__}={value!r}. Example: value={prop.example!r}."
            )
        return True, None

    if expected == "int":
        if is_bool or not isinstance(value, int):
            return False, (
                f"Property '{canonical_name}' expects int, got "
                f"{type(value).__name__}={value!r}. Example: value={prop.example!r}."
            )
        return True, None

    if expected == "float":
        if is_bool or not isinstance(value, (int, float)):
            return False, (
                f"Property '{canonical_name}' expects float, got "
                f"{type(value).__name__}={value!r}. Example: value={prop.example!r}."
            )
        return True, None

    return True, None


def known_properties() -> list[dict[str, object]]:
    return [
        {
            "canonical": prop.canonical,
            "aliases": sorted(set(prop.extra_aliases)),
            "description": prop.description,
            "value_type": prop.value_type,
            "example": prop.example,
            "scopes": list(prop.scopes),
        }
        for prop in COMMON_BUS_ELEMENT_PROPERTIES
    ]
