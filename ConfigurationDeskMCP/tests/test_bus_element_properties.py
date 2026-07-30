# -*- coding: utf-8 -*-
"""Unit tests for the bus-element / matrix property catalog and validation."""

from __future__ import annotations

from sources.services import bus_element_properties as bep


class TestResolvePropertyName:
    def test_alias_resolves_to_canonical(self):
        canonical, alias = bep.resolve_property_name("Countdown Start Value")
        assert canonical == "Countdown start value"
        assert alias == "Countdown Start Value"

    def test_normalized_variants_resolve(self):
        for raw in ("countdown start value", "COUNTDOWNSTARTVALUE"):
            canonical, _ = bep.resolve_property_name(raw)
            assert canonical == "Countdown start value"

    def test_canonical_input_has_no_alias(self):
        canonical, alias = bep.resolve_property_name("Countdown start value")
        assert canonical == "Countdown start value"
        assert alias is None

    def test_unknown_name_passes_through(self):
        canonical, alias = bep.resolve_property_name("MysteryProperty")
        assert canonical == "MysteryProperty"
        assert alias is None

    def test_empty_string_passes_through(self):
        canonical, alias = bep.resolve_property_name("")
        assert canonical == ""
        assert alias is None


class TestValidatePropertyValue:
    def test_int_property_rejects_bool(self):
        ok, msg = bep.validate_property_value("Countdown start value", True)
        assert ok is False
        assert "expects int" in msg

    def test_int_property_accepts_int(self):
        ok, msg = bep.validate_property_value("Countdown start value", 15)
        assert ok is True
        assert msg is None

    def test_bool_property_rejects_int(self):
        ok, msg = bep.validate_property_value("Recalculate SecOC information", 1)
        assert ok is False
        assert "expects bool" in msg

    def test_bool_property_accepts_bool(self):
        ok, _ = bep.validate_property_value("Recalculate SecOC information", False)
        assert ok is True

    def test_scalar_property_accepts_any_value(self):
        assert bep.validate_property_value("Initial value", "abc")[0] is True
        assert bep.validate_property_value("Initial value", 255)[0] is True
        assert bep.validate_property_value("Initial value", True)[0] is True

    def test_scope_mismatch_skips_validation(self):
        # 'Countdown start value' is bus_config-only; validating under the
        # matrix scope must not reject an otherwise invalid value.
        ok, msg = bep.validate_property_value("Countdown start value", True, scope="matrix")
        assert ok is True
        assert msg is None

    def test_scope_match_still_validates(self):
        ok, _ = bep.validate_property_value("Countdown start value", True, scope="bus_config")
        assert ok is False

    def test_unknown_property_passes_through(self):
        ok, msg = bep.validate_property_value("Unknown", object())
        assert ok is True
        assert msg is None


class TestKnownProperties:
    def test_catalog_is_serializable_and_complete(self):
        catalog = bep.known_properties()
        assert len(catalog) == len(bep.COMMON_BUS_ELEMENT_PROPERTIES)
        length = next(e for e in catalog if e["canonical"] == "Length")
        assert length["value_type"] == "int"
        assert set(("bus_config", "matrix")) == set(length["scopes"])

    def test_length_alias_resolves(self):
        canonical, alias = bep.resolve_property_name("Frame Length")
        assert canonical == "Length"
        assert alias == "Frame Length"
