# -*- coding: utf-8 -*-
"""Canonical function-port property names and GUI alias resolution.

Single source of truth for both:

* Runtime alias resolution in
  :func:`sources.services.bus_config_service.set_function_port_property`.
* The ``configurationdesk://reference/function-port-properties`` MCP
  resource exposed in :mod:`sources.resources.domain_resources`.

Each entry maps a canonical automation-API property name (the string
expected by ``FunctionPort.Properties.Item(<name>)`` in the ConfigurationDesk
COM API) to its GUI/workflow display label and a short description. Common
aliases for each property are derived automatically from the GUI label, but
extra aliases can be listed explicitly when the docs use additional names.

Sources:

* ConfigurationDesk Function Block Properties reference (GUI labels).
* ConfigurationDesk Automating Tool Handling — Examples of Automating Bus
  Manager Features (canonical property names, e.g. ``IsMappable``,
  ``IsTestAutomationSupportEnabled``, ``InitialValue``).
"""

from __future__ import annotations

from typing import Optional


class _Prop:
    """Metadata for a single function-port property."""

    __slots__ = (
        "canonical",
        "gui_label",
        "description",
        "extra_aliases",
        "read_only",
        "value_type",
        "example",
    )

    def __init__(
        self,
        canonical: str,
        gui_label: str,
        description: str,
        extra_aliases: tuple[str, ...] = (),
        read_only: bool = False,
        value_type: str = "bool",
        example: object = None,
    ) -> None:
        self.canonical = canonical
        self.gui_label = gui_label
        self.description = description
        self.extra_aliases = extra_aliases
        self.read_only = read_only
        self.value_type = value_type
        self.example = example


# Canonical catalog. Order is preserved for the rendered resource.
FUNCTION_PORT_PROPERTIES: tuple[_Prop, ...] = (
    # ── Boolean properties (Enabled / Disabled) ─────────────────────────────
    _Prop(
        canonical="IsMappable",
        gui_label="Model access",
        description=(
            "Enables/disables access to the behavior model via model port "
            "mapping. When disabled, the port cannot be mapped to model port "
            "blocks and existing mappings are deleted."
        ),
        extra_aliases=("Mappable",),
        value_type="bool",
        example=True,
    ),
    _Prop(
        canonical="IsTestAutomationSupportEnabled",
        gui_label="Activate test automation support",
        description=(
            "Provides an intervention point for test automation. When "
            "enabled, the experiment software exposes a TA switch that "
            "toggles between the original signal and a substitute value."
        ),
        extra_aliases=(
            "Test automation support",
            "Enable test automation support",
            "TA support",
        ),
        value_type="bool",
        example=True,
    ),
    # ── Integer / enum properties ────────────────────────────────────────────
    _Prop(
        canonical="InitialSwitchSetting",
        gui_label="Initial switch setting",
        description=(
            "Initial setting of the test automation (TA) switch. "
            "Integer enum: 0 = Substitute value, 1 = I/O signal "
            "(outports only), 2 = Model signal (inports only). "
            "Requires IsTestAutomationSupportEnabled = True."
        ),
        extra_aliases=("TA switch initial setting",),
        value_type="int",
        example=1,
    ),
    _Prop(
        canonical="InitialValueUsage",
        gui_label="Initial value usage",
        description=(
            "Controls when the initial value is applied. "
            "Integer enum: 0 = Each application start, "
            "1 = First application start only."
        ),
        value_type="int",
        example=0,
    ),
    _Prop(
        canonical="StoppedStatusOutput",
        gui_label="Stopped status output",
        description=(
            "Selects what the port outputs when the application stops. "
            "Integer enum: 0 = Use configured stop value, "
            "1 = Keep last run-time value."
        ),
        value_type="int",
        example=0,
    ),
    _Prop(
        canonical="Access_mode",
        gui_label="Access mode",
        description=(
            "Bus feature access mode for BusPduRawDataAccess and similar "
            "features. Integer enum: 0 = Read, 2 = Write. "
            "Note the underscore in the canonical name."
        ),
        value_type="int",
        example=0,
    ),
    _Prop(
        canonical="PortType",
        gui_label="Port type",
        description=(
            "Read-only integer enum identifying the port category "
            "(e.g. inport, outport, feature port)."
        ),
        read_only=True,
        value_type="int",
        example=None,
    ),
    # ── Numeric (float) properties ───────────────────────────────────────────
    _Prop(
        canonical="InitialValue",
        gui_label="Initial value",
        description=(
            "Value applied during system initialization and used as the "
            "default until the behavior model provides new values. Type "
            "depends on the port's data type (float, int, or vector)."
        ),
        value_type="float",
        example=1.0,
    ),
    _Prop(
        canonical="InitialSubstituteValue",
        gui_label="Initial substitute value",
        description=(
            "Substitute value used when the TA switch is set to "
            "'Substitute value'. Requires IsTestAutomationSupportEnabled = True."
        ),
        extra_aliases=("Substitute value",),
        value_type="float",
        example=0.0,
    ),
    _Prop(
        canonical="StopValue",
        gui_label="Stop value",
        description=(
            "Value output when the real-time application is stopped. Only "
            "active when StoppedStatusOutput = 0 (Use configured stop value)."
        ),
        value_type="float",
        example=0.0,
    ),
    # ── String properties ────────────────────────────────────────────────────
    _Prop(
        canonical="Description",
        gui_label="Description",
        description="Free-form user description of the function port.",
        value_type="str",
        example="My description",
    ),
    _Prop(
        canonical="Name",
        gui_label="Name",
        description="Display name of the function port.",
        value_type="str",
        example="MyPort",
    ),
)


def _normalize(value: str) -> str:
    """Strip non-alphanumeric characters and lowercase ``value``."""
    if not value:
        return ""
    return "".join(ch.lower() for ch in value if ch.isalnum())


def _build_alias_map() -> dict[str, str]:
    """Construct the lookup table mapping normalized aliases to canonical names.

    Aliases registered for each property:

    * The canonical name itself (e.g. ``IsMappable``).
    * The GUI label (e.g. ``Model access``).
    * Each explicit ``extra_aliases`` entry.

    All keys are normalized via :func:`_normalize` so callers can pass any
    casing or spacing variant (``"Model access"``, ``"model_access"``,
    ``"modelaccess"`` all resolve to ``IsMappable``).
    """
    table: dict[str, str] = {}
    for prop in FUNCTION_PORT_PROPERTIES:
        for raw in (prop.canonical, prop.gui_label, *prop.extra_aliases):
            key = _normalize(raw)
            if not key:
                continue
            # First registration wins; later duplicates are ignored so the
            # canonical name listed first in the catalog stays authoritative.
            table.setdefault(key, prop.canonical)
    return table


_ALIAS_MAP: dict[str, str] = _build_alias_map()

# Lookup by canonical name for validation.
_PROPERTIES_BY_CANONICAL: dict[str, _Prop] = {
    prop.canonical: prop for prop in FUNCTION_PORT_PROPERTIES
}


def validate_property_value(
    canonical_name: str, value: bool | int | float | str
) -> tuple[bool, str | None]:
    """Validate that *value* is compatible with the property's declared type.

    Returns ``(True, None)`` when the value is acceptable.
    Returns ``(False, error_message)`` when the type is wrong.

    Unknown property names pass through unchanged so the COM layer can
    handle future properties not yet listed in this catalog.

    Python's ``bool`` is a subclass of ``int``, so ``True``/``False`` are
    explicitly rejected for any property whose ``value_type`` is not
    ``"bool"`` — even though ``isinstance(True, int)`` is ``True``.
    """
    prop = _PROPERTIES_BY_CANONICAL.get(canonical_name)
    if prop is None:
        return True, None

    expected = prop.value_type
    is_bool = isinstance(value, bool)

    if expected == "bool":
        if not is_bool:
            return False, (
                f"Property '{canonical_name}' ('{prop.gui_label}') expects bool "
                f"(true or false), got {type(value).__name__}={value!r}. "
                f"Example: value=true."
            )
        return True, None

    if expected == "int":
        if is_bool or not isinstance(value, int):
            return False, (
                f"Property '{canonical_name}' ('{prop.gui_label}') expects int "
                f"(integer enum code), got {type(value).__name__}={value!r}. "
                f"Example: value={prop.example!r}. "
                f"See configurationdesk://reference/function-port-properties "
                f"for valid codes."
            )
        return True, None

    if expected == "float":
        if is_bool or not isinstance(value, (int, float)):
            return False, (
                f"Property '{canonical_name}' ('{prop.gui_label}') expects float "
                f"(numeric), got {type(value).__name__}={value!r}. "
                f"Example: value={prop.example!r}. "
                f"See configurationdesk://reference/function-port-properties."
            )
        return True, None

    if expected == "str":
        if not isinstance(value, str):
            return False, (
                f"Property '{canonical_name}' ('{prop.gui_label}') expects str, "
                f"got {type(value).__name__}={value!r}. "
                f"Example: value={prop.example!r}."
            )
        return True, None

    return True, None


def normalize_property_value(
    canonical_name: str, value: bool | int | float | str
) -> bool | int | float | str:
    """Normalize compatibility values for known function-port properties.

    Some tool stacks serialize boolean arguments as ``0``/``1`` even when the
    model emitted ``true``/``false``. Coerce only known bool properties and only
    for those two sentinel integer values so other enum-like integer properties
    keep their original meaning.
    """
    prop = _PROPERTIES_BY_CANONICAL.get(canonical_name)
    if prop is None or prop.value_type != "bool":
        return value

    if isinstance(value, bool):
        return value

    if isinstance(value, int) and value in (0, 1):
        return bool(value)

    return value


def resolve_property_name(property_name: str) -> tuple[str, Optional[str]]:
    """Resolve ``property_name`` to its canonical automation-API name.

    Returns ``(canonical, alias_used)`` where ``alias_used`` is ``None`` when
    ``property_name`` was already canonical (or unknown — passed through
    unchanged) and the original input string otherwise. Callers can use
    ``alias_used`` to surface the rewrite in user-facing messages.
    """
    if not property_name:
        return property_name, None
    canonical = _ALIAS_MAP.get(_normalize(property_name))
    if canonical and canonical != property_name:
        return canonical, property_name
    return property_name, None


def known_aliases() -> list[dict[str, object]]:
    """Return a JSON-serializable catalog of all known properties + aliases.

    Used by the MCP resource so clients can introspect what GUI labels and
    workflow names map to which canonical property names.
    """
    catalog: list[dict[str, object]] = []
    for prop in FUNCTION_PORT_PROPERTIES:
        aliases = sorted({prop.gui_label, *prop.extra_aliases} - {prop.canonical})
        catalog.append(
            {
                "canonical": prop.canonical,
                "gui_label": prop.gui_label,
                "aliases": aliases,
                "description": prop.description,
                "value_type": prop.value_type,
                "example": prop.example,
                "read_only": prop.read_only,
            }
        )
    return catalog
