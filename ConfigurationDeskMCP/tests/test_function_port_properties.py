# -*- coding: utf-8 -*-
"""Unit tests for the function-port property catalog and alias resolution."""

from __future__ import annotations

from sources.services import function_port_properties as fpp


class TestResolvePropertyName:
    def test_gui_label_resolves_to_canonical(self):
        canonical, alias = fpp.resolve_property_name("Model access")
        assert canonical == "IsMappable"
        assert alias == "Model access"

    def test_normalized_variants_resolve(self):
        for raw in ("model_access", "MODELACCESS", "  Model Access  "):
            canonical, _ = fpp.resolve_property_name(raw)
            assert canonical == "IsMappable"

    def test_canonical_input_is_passed_through_without_alias(self):
        canonical, alias = fpp.resolve_property_name("IsMappable")
        assert canonical == "IsMappable"
        assert alias is None

    def test_unknown_name_passes_through_unchanged(self):
        canonical, alias = fpp.resolve_property_name("TotallyUnknownProperty")
        assert canonical == "TotallyUnknownProperty"
        assert alias is None

    def test_empty_string_passes_through(self):
        canonical, alias = fpp.resolve_property_name("")
        assert canonical == ""
        assert alias is None


class TestValidatePropertyValue:
    def test_bool_property_accepts_bool(self):
        ok, msg = fpp.validate_property_value("IsMappable", True)
        assert ok is True
        assert msg is None

    def test_bool_property_rejects_int(self):
        ok, msg = fpp.validate_property_value("IsMappable", 1)
        assert ok is False
        assert "expects bool" in msg

    def test_int_property_rejects_bool(self):
        ok, msg = fpp.validate_property_value("InitialSwitchSetting", True)
        assert ok is False
        assert "expects int" in msg

    def test_int_property_accepts_int(self):
        ok, msg = fpp.validate_property_value("InitialSwitchSetting", 1)
        assert ok is True
        assert msg is None

    def test_float_property_accepts_int_and_float(self):
        assert fpp.validate_property_value("InitialValue", 1)[0] is True
        assert fpp.validate_property_value("InitialValue", 1.5)[0] is True

    def test_float_property_rejects_bool(self):
        ok, msg = fpp.validate_property_value("InitialValue", True)
        assert ok is False
        assert "expects float" in msg

    def test_str_property_rejects_non_str(self):
        ok, msg = fpp.validate_property_value("Description", 5)
        assert ok is False
        assert "expects str" in msg

    def test_unknown_property_passes_through(self):
        ok, msg = fpp.validate_property_value("Unknown", object())
        assert ok is True
        assert msg is None


class TestNormalizePropertyValue:
    def test_bool_property_coerces_zero_and_one(self):
        assert fpp.normalize_property_value("IsMappable", 1) is True
        assert fpp.normalize_property_value("IsMappable", 0) is False

    def test_bool_property_leaves_actual_bool(self):
        assert fpp.normalize_property_value("IsMappable", True) is True

    def test_bool_property_leaves_out_of_range_int(self):
        assert fpp.normalize_property_value("IsMappable", 2) == 2

    def test_non_bool_property_is_not_coerced(self):
        assert fpp.normalize_property_value("InitialSwitchSetting", 1) == 1
        assert fpp.normalize_property_value("InitialSwitchSetting", 1) is not True

    def test_unknown_property_is_not_coerced(self):
        assert fpp.normalize_property_value("Unknown", 1) == 1


class TestKnownAliases:
    def test_catalog_is_serializable_and_complete(self):
        catalog = fpp.known_aliases()
        assert len(catalog) == len(fpp.FUNCTION_PORT_PROPERTIES)
        entry = next(e for e in catalog if e["canonical"] == "IsMappable")
        assert entry["gui_label"] == "Model access"
        assert entry["value_type"] == "bool"
        assert "Mappable" in entry["aliases"]
        assert entry["canonical"] not in entry["aliases"]

    def test_read_only_flag_is_exposed(self):
        catalog = fpp.known_aliases()
        port_type = next(e for e in catalog if e["canonical"] == "PortType")
        assert port_type["read_only"] is True
