# -*- coding: utf-8 -*-
"""Domain: bus configuration tools (sources/tools/bus_config.py).

Covers every bus-configuration tool at the service layer (through the fake
bridge) plus the bus-config COM behavior (function-port and feature-node
property setting) and value-validation edge cases.
"""

from __future__ import annotations

import asyncio
import json

from configurationdesk_com_bridge.domains import bus_config_com
from sources.services import bus_config_service as bus_svc

from tests.domains.conftest import run_ok, run_raw

COVERS = (
    "create_bus_configuration",
    "remove_bus_configuration",
    "list_bus_configurations",
    "assign_matrix_to_bus_config",
    "assign_ecu_to_bus_config",
    "add_feature_to_bus_element",
    "remove_bus_config_elements",
    "generate_bus_containers",
    "find_bus_config_elements",
    "assign_bus_config_to_application_process",
    "set_function_port_property",
    "set_bus_config_element_property",
)


# ── Service-layer tool coverage ────────────────────────────────────────────


def test_create_bus_configuration(fake_bridge):
    payload = run_ok(bus_svc.create("RestbusBusConfig"))
    assert payload["name"] == "RestbusBusConfig"


def test_create_bus_configuration_reports_readback_name_mismatch(monkeypatch):
    class _CreatedBusConfiguration:
        Name = "Bus Configuration (1)"

        def __setattr__(self, name, value):
            if name != "Name":
                super().__setattr__(name, value)

    class _Relation:
        def GetCreatableTypes(self):
            return type("_Types", (), {"Item": lambda self, index: object()})()

        def CreateDataObject(self, data_type):
            return _CreatedBusConfiguration()

        def GetTopNodes(self):
            return [_CreatedBusConfiguration()]

    connection = type(
        "_Connection",
        (),
        {"relations": type("_Relations", (), {"Item": lambda self, name: _Relation()})()},
    )()

    result = bus_config_com.create(connection, "dummy_bus_config")

    assert result["verified"] is False
    assert result["name"] == "Bus Configuration (1)"
    assert "does not match requested name" in result["detail"]


def test_create_bus_configuration_returns_error_for_readback_name_mismatch(monkeypatch):
    connection = object()

    async def fake_dispatch(function, passed_connection, name):
        assert function is bus_config_com.create
        assert passed_connection is connection
        assert name == "dummy_bus_config"
        return {
            "name": "Bus Configuration (1)",
            "verified": False,
            "detail": "Created bus configuration name does not match requested name.",
        }

    monkeypatch.setattr(bus_svc, "get_connection", lambda: connection)
    monkeypatch.setattr(bus_svc, "dispatch", fake_dispatch)

    payload = run_raw(bus_svc.create("dummy_bus_config"))

    assert payload["success"] is False
    assert payload["retryable"] is False


def test_remove_bus_configuration(fake_bridge):
    run_ok(bus_svc.remove("RestbusBusConfig"))


def test_list_bus_configurations(fake_bridge):
    run_ok(bus_svc.list_configs())


def test_assign_matrix_to_bus_config(fake_bridge):
    run_ok(bus_svc.assign_matrix("RestbusBusConfig", element_name="CanBodyCluster", part="all"))


def test_assign_ecu_to_bus_config(fake_bridge):
    run_ok(
        bus_svc.assign_ecu(
            bus_config_name="RestbusBusConfig", ecu_names=["CentralGatewayEcu"], part="simulated"
        )
    )


def test_add_feature_to_bus_element(fake_bridge):
    run_ok(
        bus_svc.add_feature(
            "BusISignalValueAccess",
            element_name="CentralGatewayEcu",
            bus_config_name="RestbusBusConfig",
        )
    )


def test_remove_bus_config_elements(fake_bridge):
    run_ok(bus_svc.remove_elements(element_name="CentralGatewayEcu"))


def test_generate_bus_containers(fake_bridge):
    # Container generation reports success but is intentionally unverified.
    payload = run_raw(bus_svc.generate_containers())
    assert payload["success"] is True


def test_find_bus_config_elements(fake_bridge):
    payload = run_ok(bus_svc.find_elements(xpath='//*[@Name="RestbusBusConfig"]//FunctionPort'))
    assert payload["count"] == payload["total_count"] == 1
    assert payload["returned_count"] == 1
    assert payload["next_offset"] is None


def test_find_bus_config_elements_paginates(fake_bridge):
    payload = run_ok(
        bus_svc.find_elements(
            xpath='//*[@Name="RestbusBusConfig"]//FunctionPort', offset=1, limit=1
        )
    )

    assert payload["elements"] == []
    assert payload["count"] == payload["total_count"] == 1
    assert payload["returned_count"] == 0
    assert payload["next_offset"] is None


def test_assign_bus_config_to_application_process(fake_bridge):
    run_ok(bus_svc.assign_to_application_process("RestbusBusConfig"))


def test_set_function_port_property(fake_bridge):
    run_ok(
        bus_svc.set_function_port_property("IsMappable", True, bus_config_name="RestbusBusConfig")
    )


def test_set_bus_config_element_property(fake_bridge):
    run_ok(
        bus_svc.set_bus_config_element_property(
            "Countdown Start Value", 15, element_name="Frame Length"
        )
    )


# ── Service-layer value validation ─────────────────────────────────────────


def test_set_function_port_property_rejects_bool_for_float(monkeypatch):
    async def fail_dispatch(*args, **kwargs):  # pragma: no cover - should not run
        raise AssertionError("dispatch should not be called for invalid value types")

    monkeypatch.setattr(bus_svc, "dispatch", fail_dispatch)

    payload = json.loads(asyncio.run(bus_svc.set_function_port_property("InitialValue", True)))

    assert payload["success"] is False
    assert payload["error_code"] == "INVALID_VALUE_TYPE"
    assert "expects float" in payload["error"]


def test_set_function_port_property_normalizes_int_bool_compatibility_values(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_dispatch(*args, **kwargs):
        captured["args"] = args
        return {"set_count": 1, "verified_count": 1, "mismatch_count": 0}

    monkeypatch.setattr(bus_svc, "dispatch", fake_dispatch)
    monkeypatch.setattr(bus_svc, "get_connection", lambda: object())

    payload = json.loads(asyncio.run(bus_svc.set_function_port_property("Model access", 1)))

    assert payload["success"] is True
    assert "resolved to 'IsMappable'" in payload["message"]
    assert captured["args"][2] == "IsMappable"
    assert captured["args"][3] is True


def test_set_function_port_property_rejects_non_compatibility_int_for_bool(monkeypatch):
    async def fail_dispatch(*args, **kwargs):  # pragma: no cover - should not run
        raise AssertionError("dispatch should not be called for invalid value types")

    monkeypatch.setattr(bus_svc, "dispatch", fail_dispatch)

    payload = json.loads(asyncio.run(bus_svc.set_function_port_property("Model access", 2)))

    assert payload["success"] is False
    assert payload["error_code"] == "INVALID_VALUE_TYPE"
    assert "expects bool" in payload["error"]


def test_set_function_port_property_preserves_int_enum_values(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_dispatch(*args, **kwargs):
        captured["args"] = args
        return {"set_count": 1, "verified_count": 1, "mismatch_count": 0}

    monkeypatch.setattr(bus_svc, "dispatch", fake_dispatch)
    monkeypatch.setattr(bus_svc, "get_connection", lambda: object())

    payload = json.loads(asyncio.run(bus_svc.set_function_port_property("InitialSwitchSetting", 1)))

    assert payload["success"] is True
    assert captured["args"][2] == "InitialSwitchSetting"
    assert captured["args"][3] == 1
    assert captured["args"][3] is not True


def test_set_function_port_property_preserves_structured_port_discovery_guidance(monkeypatch):
    async def fake_dispatch(*args, **kwargs):
        return {
            "error": True,
            "detail": "No function-port property nodes found for XPath: //FunctionPort/@IsMappable",
            "error_code": "FUNCTION_PORT_PROPERTY_NOT_FOUND",
            "retryable": False,
            "recovery_hint": (
                "Inspect the function ports with find_bus_config_elements before retrying. "
                "Do NOT call generate_bus_containers just to make the function port appear."
            ),
            "next_action": (
                "Call `find_bus_config_elements`, verify the exact function-port XPath, then retry "
                "`set_function_port_property`."
            ),
        }

    monkeypatch.setattr(bus_svc, "dispatch", fake_dispatch)
    monkeypatch.setattr(bus_svc, "get_connection", lambda: object())

    payload = json.loads(asyncio.run(bus_svc.set_function_port_property("IsMappable", True)))

    assert payload["success"] is False
    assert payload["error_code"] == "FUNCTION_PORT_PROPERTY_NOT_FOUND"
    assert payload["retryable"] is False
    assert "find_bus_config_elements" in payload["recovery_hint"]
    assert "find_bus_config_elements" in payload["next_action"]


def test_set_bus_config_element_property_rejects_bool_for_int(monkeypatch):
    async def fail_dispatch(*args, **kwargs):  # pragma: no cover - should not run
        raise AssertionError("dispatch should not be called for invalid value types")

    monkeypatch.setattr(bus_svc, "dispatch", fail_dispatch)

    payload = json.loads(
        asyncio.run(bus_svc.set_bus_config_element_property("Countdown Start Value", True))
    )

    assert payload["success"] is False
    assert payload["error_code"] == "INVALID_VALUE_TYPE"
    assert "expects int" in payload["error"]


# ── COM-layer behavior (bus_config_com) ────────────────────────────────────


class _FakeProperty:
    def __init__(self, initial_value=None, accept=True):
        self.Value = initial_value
        self._accept = accept
        self.calls: list[object] = []

    def TrySetValue(self, value):
        self.calls.append(value)
        if not self._accept:
            return False
        self.Value = value
        return True


class _FakePropertyCollection:
    def __init__(self, mapping):
        self._mapping = mapping
        self.Count = len(mapping)
        for name, handle in mapping.items():
            if not hasattr(handle, "Name"):
                handle.Name = name

    def __getitem__(self, key):
        return self._mapping[key]

    def Item(self, key):
        if isinstance(key, int):
            return list(self._mapping.values())[key]
        return self._mapping[key]


class _FakePropertyContainer:
    def __init__(self, mapping):
        self.Properties = _FakePropertyCollection(mapping)


class _FakeNamedNode(_FakePropertyContainer):
    def __init__(self, name, mapping, roles=None):
        super().__init__(mapping)
        self.Name = name
        self.Roles = roles or []


class _FakeRelation:
    def __init__(self, props):
        self._props = props
        self.xpaths: list[str] = []

    def FindByXPath(self, xpath, _context):
        self.xpaths.append(xpath)
        return list(self._props)


class _FakeXPathAwareRelation:
    def __init__(self, props_by_xpath):
        self._props_by_xpath = props_by_xpath
        self.xpaths: list[str] = []

    def FindByXPath(self, xpath, _context):
        self.xpaths.append(xpath)
        return list(self._props_by_xpath.get(xpath, []))


class _FakeRelations:
    def __init__(self, relation):
        self._relation = relation

    def Item(self, name):
        assert name == "BusConfigurationsWithProperties"
        return self._relation


class _FakeConnection:
    def __init__(self, relation):
        self.relations = _FakeRelations(relation)


class _FakeCoercingProperty(_FakeProperty):
    def TrySetValue(self, value):
        self.calls.append(value)
        if not self._accept:
            return False
        if value in (0, 0.0):
            self.Value = False
        elif value in (1, 1.0):
            self.Value = True
        else:
            self.Value = value
        return True


def test_set_function_port_property_handles_direct_and_nested_property_nodes():
    direct_prop = _FakeProperty(initial_value=False)
    nested_prop = _FakeProperty(initial_value=False)
    nested_container = _FakePropertyContainer({"IsMappable": nested_prop})
    relation = _FakeRelation([direct_prop, nested_container])
    connection = _FakeConnection(relation)

    result = bus_config_com.set_function_port_property(
        connection,
        "IsMappable",
        True,
        bus_config_name="BusConfig1",
    )

    assert result["set_count"] == 2
    assert result["fail_count"] == 0
    assert result["verified_count"] == 2
    assert result["mismatch_count"] == 0
    assert direct_prop.calls == [True]
    assert nested_prop.calls == [True]
    assert relation.xpaths == ['//BusConfiguration[@Name="BusConfig1"]//FunctionPort/@IsMappable']


def test_set_function_port_property_does_not_treat_non_bool_truthy_values_as_match():
    prop = _FakeProperty(initial_value=1, accept=True)
    relation = _FakeRelation([prop])
    connection = _FakeConnection(relation)

    result = bus_config_com.set_function_port_property(connection, "InitialSwitchSetting", 2)

    assert result["set_count"] == 1
    assert result["verified_count"] == 1
    assert result["mismatch_count"] == 0
    assert prop.calls == [2]


def test_set_function_port_property_missing_nodes_guides_port_discovery():
    relation = _FakeRelation([])
    connection = _FakeConnection(relation)

    result = bus_config_com.set_function_port_property(
        connection,
        "IsMappable",
        True,
        bus_config_name="BusConfig1",
    )

    assert result["error"] is True
    assert result["error_code"] == "FUNCTION_PORT_PROPERTY_NOT_FOUND"
    assert result["retryable"] is False
    assert "find_bus_config_elements" in result["recovery_hint"]
    assert "Do NOT call generate_bus_containers" in result["recovery_hint"]
    assert "find_bus_config_elements" in result["next_action"]


def test_set_function_port_property_feature_type_alias_resolves_to_concrete_feature_xpath():
    prop = _FakeProperty(initial_value=False)
    alias_xpath = (
        '//BusConfiguration[@Name="BusConfig1"]//BusISignalValueAccess//FunctionPort/@IsMappable'
    )
    relation = _FakeXPathAwareRelation({alias_xpath: [prop]})
    connection = _FakeConnection(relation)

    result = bus_config_com.set_function_port_property(
        connection,
        "IsMappable",
        True,
        bus_config_name="BusConfig1",
        feature_type="ISignalValue",
    )

    assert result["set_count"] == 1
    assert result["verified_count"] == 1
    assert result["mismatch_count"] == 0
    assert relation.xpaths == [alias_xpath]


def test_set_function_port_property_treats_false_readback_as_numeric_zero_for_mixed_ports():
    prop = _FakeCoercingProperty(initial_value=False)
    relation = _FakeRelation([prop])
    connection = _FakeConnection(relation)

    result = bus_config_com.set_function_port_property(
        connection,
        "InitialSubstituteValue",
        0.0,
        bus_config_name="BusConfig1",
    )

    assert result["set_count"] == 1
    assert result["verified_count"] == 1
    assert result["mismatch_count"] == 0
    assert prop.calls == [0.0]


def test_set_bus_config_element_property_sets_feature_property_by_alias():
    countdown_prop = _FakeProperty(initial_value=0)
    feature_node = _FakeNamedNode(
        "Frame Length",
        {"Countdown start value": countdown_prop},
        roles=["BusFeature", "BusFrameLengthManipulation"],
    )
    relation = _FakeRelation([feature_node])
    connection = _FakeConnection(relation)

    result = bus_config_com.set_bus_config_element_property(
        connection,
        "Countdown Start Value",
        15,
        element_name="Frame Length",
    )

    assert result["set_count"] == 1
    assert result["verified_count"] == 1
    assert result["mismatch_count"] == 0
    assert result["property_name"] == "Countdown start value"
    assert countdown_prop.calls == [15]


def test_set_bus_config_element_property_requires_allow_multiple_for_ambiguous_matches():
    first = _FakeNamedNode("Frame Length", {"Length": _FakeProperty(initial_value=2)})
    second = _FakeNamedNode("Frame Length", {"Length": _FakeProperty(initial_value=2)})
    relation = _FakeRelation([first, second])
    connection = _FakeConnection(relation)

    result = bus_config_com.set_bus_config_element_property(
        connection,
        "Length",
        1,
        element_name="Frame Length",
    )

    assert result["error"] is True
    assert "allow_multiple=true" in result["detail"]
