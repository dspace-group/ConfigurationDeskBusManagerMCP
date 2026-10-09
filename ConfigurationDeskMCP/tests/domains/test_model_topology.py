# -*- coding: utf-8 -*-
"""Domain: model topology tools (sources/tools/model_topology.py)."""

from __future__ import annotations

from types import SimpleNamespace

from configurationdesk_com_bridge.domains import model_topology_com
from sources.services import model_topology_service as model_svc

from tests.domains.conftest import run_ok, run_raw

COVERS = (
    "add_model",
    "replace_model",
    "remove_model",
    "analyze_models",
    "create_application_process",
    "list_models",
    "add_model_to_signal_chain",
    "add_model_port_block_to_signal_chain",
    "list_model_port_blocks",
    "list_model_ports",
)


def test_add_model(fake_bridge):
    payload = run_ok(model_svc.add_model("CentralGatewayECU_64-bit.sic", analyze=False))
    assert "CentralGatewayECU_64-bit" in payload["added"]


def test_replace_model(fake_bridge):
    run_ok(model_svc.replace_model("CentralGatewayECU_64-bit.sic", "CentralGatewayECU_64-bit"))


def test_remove_model(fake_bridge):
    run_ok(model_svc.remove_model("CentralGatewayECU_64-bit"))


def test_analyze_models(fake_bridge):
    run_ok(model_svc.analyze_models())


def test_create_application_process(fake_bridge):
    run_ok(model_svc.create_application_process())


def test_list_models(fake_bridge):
    run_ok(model_svc.list_models())


def test_add_model_to_signal_chain(fake_bridge):
    run_ok(model_svc.add_model_to_signal_chain("demosmd_io"))


def test_add_model_port_block_to_signal_chain(fake_bridge):
    run_ok(model_svc.add_model_port_block_to_signal_chain("demosmd_io", "In1"))


def test_list_model_port_blocks(fake_bridge):
    payload = run_ok(model_svc.list_model_port_blocks("demosmd_io"))
    assert payload["count"] == 2


def test_list_model_ports(fake_bridge):
    payload = run_ok(model_svc.list_model_ports("demosmd_io"))
    assert payload["count"] == 2
    assert payload["ports"][0]["port_block_name"] == "In1"
    assert payload["ports"][0]["port_type"] == "In"


def test_list_model_ports_scoped_to_one_port_block(fake_bridge):
    payload = run_ok(model_svc.list_model_ports("demosmd_io", "In1"))
    assert payload["port_blocks_scanned"] == ["In1"]


def test_list_model_ports_rejects_unknown_port_block(fake_bridge):
    payload = run_raw(model_svc.list_model_ports("demosmd_io", "NoSuchBlock"))
    assert payload["success"] is False
    assert "NoSuchBlock" in payload["error"]


# ── COM-layer behavior (model_topology_com) ────────────────────────────────


class _FakeCollection:
    def __init__(self, items):
        self._items = list(items)
        self.Count = len(self._items)

    def Item(self, index):
        if index == 0:
            return self._items[0]
        if 1 <= index <= len(self._items):
            return self._items[index - 1]
        return self._items[index]

    def __iter__(self):
        return iter(self._items)


def test_resolve_processing_unit_application_recovers_when_hardware_exists():
    exec_app = SimpleNamespace(Name="RestbusApp", Roles=["ExecutableApplication"])
    container = SimpleNamespace(Name="Container", Roles=["SomethingElse"])
    processing_unit = SimpleNamespace(
        Name="ProcessingUnitApplication", Roles=["ProcessingUnitApplication"]
    )

    class _FakeRelation:
        def GetTopNodes(self):
            return _FakeCollection([exec_app])

        def GetElements(self, parent):
            if parent is exec_app:
                return _FakeCollection([container])
            if parent is container:
                return _FakeCollection([processing_unit])
            return _FakeCollection([])

    pua, detail = model_topology_com._resolve_processing_unit_application(
        SimpleNamespace(),
        _FakeRelation(),
    )

    assert pua is processing_unit
    assert detail == ""


def test_resolve_processing_unit_application_still_fails_without_processing_unit():
    exec_app = SimpleNamespace(Name="RestbusApp", Roles=["ExecutableApplication"])

    class _FakeRelation:
        def GetTopNodes(self):
            return _FakeCollection([exec_app])

        def GetElements(self, _parent):
            return _FakeCollection([])

    pua, detail = model_topology_com._resolve_processing_unit_application(
        SimpleNamespace(),
        _FakeRelation(),
    )

    assert pua is None
    assert (
        "No ProcessingUnitApplication is available under the active executable application"
        in detail
    )


# ── Model port block hierarchy (subsystems) ────────────────────────────────


class _Props:
    def __init__(self, names):
        self._handles = [SimpleNamespace(Name=name, Value=None) for name in names]
        self.Count = len(self._handles)

    def Item(self, index):
        return self._handles[index]


class _TopologyNode:
    """Model topology node exposing a property set like the real COM objects."""

    def __init__(self, name, props, children=()):
        self.Name = name
        self.Properties = _Props(props)
        self.IsInApplication = False
        self._children = list(children)

    def __iter__(self):
        return iter(self._children)

    def Item(self, key):
        for child in self._children:
            if child.Name == key:
                return child
        raise KeyError(key)


_SUBSYSTEM_PROPS = ["Name"]
_BLOCK_PROPS = ["Name", "Source type", "Source name", "Path", "BlockID", "Description"]
_PORT_PROPS = ["Name", "SignalID", "Description", "PortType", "DataType", "DataWidth"]


def _demosmd_connection():
    """Mirror the live demosmd_io topology: 'Wavetable' at root and in 'Subsystem'."""

    def block(name, ports):
        return _TopologyNode(name, _BLOCK_PROPS, [_TopologyNode(p, _PORT_PROPS) for p in ports])

    root_wavetable = block("Wavetable", ["Wavetable Period", "Amplitude"])
    nested_wavetable = block("Wavetable", ["Wavetable Period", "Amplitude"])
    model = _TopologyNode(
        "demosmd_io",
        ["Name", "Source type"],
        [
            block("Mass displacement", ["Voltage"]),
            root_wavetable,
            _TopologyNode("Subsystem", _SUBSYSTEM_PROPS, [nested_wavetable]),
            _TopologyNode("info", _SUBSYSTEM_PROPS),
        ],
    )
    mt = _TopologyNode("mt", [], [model])
    return SimpleNamespace(model_topology=mt), root_wavetable, nested_wavetable


def test_list_model_port_blocks_recurses_into_subsystems():
    conn, _root, _nested = _demosmd_connection()

    blocks = model_topology_com.list_model_port_blocks(conn, "demosmd_io")

    assert blocks == [
        {
            "name": "Mass displacement",
            "path": "demosmd_io/Mass displacement",
            "identifier": "Mass displacement",
        },
        {"name": "Wavetable", "path": "demosmd_io/Wavetable", "identifier": "demosmd_io/Wavetable"},
        {
            "name": "Wavetable",
            "path": "demosmd_io/Subsystem/Wavetable",
            "identifier": "demosmd_io/Subsystem/Wavetable",
        },
    ]


def test_list_model_ports_by_bare_name_reports_every_hierarchy_level():
    conn, _root, _nested = _demosmd_connection()

    result = model_topology_com.list_model_ports(conn, "demosmd_io", "Wavetable")

    assert result["port_blocks_scanned"] == [
        "demosmd_io/Wavetable",
        "demosmd_io/Subsystem/Wavetable",
    ]
    assert {port["port_block_path"] for port in result["ports"]} == {
        "demosmd_io/Wavetable",
        "demosmd_io/Subsystem/Wavetable",
    }


def test_list_model_ports_does_not_treat_subsystem_as_port_block():
    conn, _root, _nested = _demosmd_connection()

    result = model_topology_com.list_model_ports(conn, "demosmd_io", "Subsystem")

    assert result["reason"] == "model_port_block_not_found"


def test_add_model_port_block_rejects_name_shared_across_hierarchy_levels():
    conn, root, nested = _demosmd_connection()

    result = model_topology_com.add_model_port_block_to_signal_chain(
        conn, "demosmd_io", "Wavetable"
    )

    assert result["reason"] == "ambiguous_model_port_block_hierarchy"
    assert result["candidates"] == ["demosmd_io/Wavetable", "demosmd_io/Subsystem/Wavetable"]
    assert root.IsInApplication is False
    assert nested.IsInApplication is False


def test_add_model_port_block_by_path_enables_only_that_block():
    conn, root, nested = _demosmd_connection()

    result = model_topology_com.add_model_port_block_to_signal_chain(
        conn, "demosmd_io", "Subsystem/Wavetable"
    )

    assert result["port_block_path"] == "demosmd_io/Subsystem/Wavetable"
    assert nested.IsInApplication is True
    assert root.IsInApplication is False


def test_list_model_port_blocks_service_flags_ambiguous_names(fake_bridge, monkeypatch):
    blocks = [
        {"name": "Wavetable", "path": "demosmd_io/Wavetable", "identifier": "demosmd_io/Wavetable"},
        {
            "name": "Wavetable",
            "path": "demosmd_io/Subsystem/Wavetable",
            "identifier": "demosmd_io/Subsystem/Wavetable",
        },
    ]

    async def fake_observation(*_args, **_kwargs):
        return blocks

    monkeypatch.setattr(model_svc, "dispatch_observation", fake_observation)

    payload = run_ok(model_svc.list_model_port_blocks("demosmd_io"))

    assert payload["port_blocks"] == ["demosmd_io/Wavetable", "demosmd_io/Subsystem/Wavetable"]
    assert payload["ambiguous_names"] == {
        "Wavetable": ["demosmd_io/Wavetable", "demosmd_io/Subsystem/Wavetable"]
    }
