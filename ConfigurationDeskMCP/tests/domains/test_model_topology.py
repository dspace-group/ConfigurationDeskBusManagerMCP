# -*- coding: utf-8 -*-
"""Domain: model topology tools (sources/tools/model_topology.py)."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

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
    "connect_model_port_to_model_port",
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
    payload = run_ok(model_svc.create_application_process())
    assert payload["provide_default_task"] is True
    assert payload["default_task_set"] is True


def test_create_application_process_without_default_task(fake_bridge):
    payload = run_ok(model_svc.create_application_process(provide_default_task=False))
    assert payload["provide_default_task"] is False
    assert payload["default_task_set"] is False
    assert "without a default task" in payload["message"]


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


def test_list_model_ports_paginates_only_leaf_ports(fake_bridge):
    payload = run_ok(model_svc.list_model_ports("demosmd_io", offset=1, limit=1))

    assert payload["count"] == 2
    assert [port["name"] for port in payload["ports"]] == ["In1", "Out1"]
    assert [port["port_path"] for port in payload["leaf_ports"]] == ["Bus/Speed"]
    assert payload["leaf_ports_page"] == {
        "total_count": 3,
        "returned_count": 1,
        "offset": 1,
        "limit": 1,
        "next_offset": 2,
    }


def test_connect_model_port_to_model_port(fake_bridge):
    payload = run_ok(
        model_svc.connect_model_port_to_model_port(
            "demosmd_io", "Out1", "Bus/Speed", "EngineAndBodyECUs_64-bit", "In1", "data1"
        )
    )

    assert payload["status"] == "compatible"
    assert payload["verified"] is True
    assert payload["warnings"] == []
    assert payload["source"]["full_path"] == "demosmd_io/Out1/Bus/Speed"


def test_connect_model_port_to_model_port_reports_ui_warning_text(fake_bridge):
    payload = run_ok(
        model_svc.connect_model_port_to_model_port(
            "demosmd_io", "FIR", "Output", "demosmd_io", "FIR", "Input"
        )
    )

    assert payload["status"] == "warning"
    assert payload["warnings"] == [
        {
            "message": (
                "Model port mapping: Invalid connection between data port blocks of same model"
            ),
            "effect": "Generate no code",
        }
    ]


def test_connect_model_port_to_model_port_returns_refusal_unchanged(fake_bridge):
    payload = run_raw(
        model_svc.connect_model_port_to_model_port(
            "demosmd_io", "Out1", "refused", "EngineAndBodyECUs_64-bit", "In1", "data1"
        )
    )

    assert payload["success"] is False
    assert payload["status"] == "error"
    assert payload["error_code"] == "MAPPING_REFUSED"
    assert payload["retryable"] is False
    assert payload["configurationdesk_message"] == (
        "ConnectObjects\r\nConnectObjects: Cannot connect \r\n; HResult; "
    )
    assert "does not report the specific reason" in payload["error"]


def test_link_warnings_ignore_new_conflicts_of_other_elements():
    result = {
        "source": {"port_name": "Output"},
        "target": {"port_name": "Input"},
        "new_conflicts": [
            {"name": "Unrelated", "context": "Function block", "effect": "", "children": []}
        ],
    }

    assert model_svc._link_warnings(result) == []


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
    assert "No ProcessingUnitApplication is available under the executable application" in detail


def _pua_relation(puas):
    exec_app = SimpleNamespace(Name="RestbusApp", Roles=["ExecutableApplication"])

    class _FakeRelation:
        def GetTopNodes(self):
            return _FakeCollection([exec_app])

        def GetElements(self, parent):
            return _FakeCollection(puas if parent is exec_app else [])

    return _FakeRelation()


def test_resolve_processing_unit_application_by_name():
    pua_1 = SimpleNamespace(Name="PUA_1", Roles=["ProcessingUnitApplication"])
    pua_2 = SimpleNamespace(Name="PUA_2", Roles=["ProcessingUnitApplication"])

    pua, detail = model_topology_com._resolve_processing_unit_application(
        SimpleNamespace(), _pua_relation([pua_1, pua_2]), "pua_2"
    )

    assert pua is pua_2
    assert detail == ""


def test_resolve_processing_unit_application_requires_name_when_several_exist():
    puas = [SimpleNamespace(Name=f"PUA_{i}", Roles=["ProcessingUnitApplication"]) for i in (1, 2)]

    pua, detail = model_topology_com._resolve_processing_unit_application(
        SimpleNamespace(), _pua_relation(puas)
    )

    assert pua is None
    assert "PUA_1, PUA_2" in detail


def test_resolve_processing_unit_application_reports_unknown_name():
    puas = [SimpleNamespace(Name="PUA_1", Roles=["ProcessingUnitApplication"])]

    pua, detail = model_topology_com._resolve_processing_unit_application(
        SimpleNamespace(), _pua_relation(puas), "Missing"
    )

    assert pua is None
    assert "'Missing' not found" in detail


# ── Processing unit application selection policy (service layer) ──────────


def _set_pua_names(monkeypatch, *name_lists):
    """Make successive list_processing_unit_application_names calls return *name_lists*."""
    from tests import _fake_bridge

    returns = _fake_bridge.dispatch_returns()
    sequence = iter(name_lists)
    calls = []

    async def fake_dispatch(fn, *args, **kwargs):
        name = fn.__name__
        calls.append(name)
        if name == "list_processing_unit_application_names":
            return next(sequence)
        handler = returns[name]
        return handler(*args[1:]) if callable(handler) else handler

    monkeypatch.setattr(model_svc, "dispatch", fake_dispatch)
    monkeypatch.setattr(model_svc, "get_connection", lambda: SimpleNamespace())
    return calls


def test_create_application_process_creates_processing_unit_application_when_none(monkeypatch):
    calls = _set_pua_names(monkeypatch, [], ["ProcessingUnitApplication"])

    payload = run_ok(model_svc.create_application_process())

    assert "add_processing_unit_application" in calls
    assert payload["processing_unit_application"] == "ProcessingUnitApplication"
    assert payload["processing_unit_application_created"] is True


def test_create_application_process_uses_single_processing_unit_application(monkeypatch):
    calls = _set_pua_names(monkeypatch, ["PUA_1"])

    payload = run_ok(model_svc.create_application_process())

    assert "add_processing_unit_application" not in calls
    assert payload["processing_unit_application"] == "PUA_1"
    assert payload["processing_unit_application_created"] is False


def test_create_application_process_requires_choice_when_several(monkeypatch):
    _set_pua_names(monkeypatch, ["PUA_1", "PUA_2"])

    payload = json.loads(asyncio.run(model_svc.create_application_process()))

    assert payload["success"] is False
    assert "processing_unit_application" in payload["next_action"]


def test_select_processing_unit_application_asks_user_when_several(monkeypatch):
    _set_pua_names(monkeypatch, ["PUA_1", "PUA_2"])
    offered = []

    async def choose(names):
        offered.extend(names)
        return "PUA_2"

    name, error = asyncio.run(model_svc.select_processing_unit_application(choose))

    assert offered == ["PUA_1", "PUA_2"]
    assert (name, error) == ("PUA_2", None)


@pytest.mark.parametrize("names", [[], ["PUA_1"]])
def test_select_processing_unit_application_does_not_ask_user(monkeypatch, names):
    _set_pua_names(monkeypatch, names)

    async def choose(_names):
        raise AssertionError("user must not be asked")

    name, error = asyncio.run(model_svc.select_processing_unit_application(choose))

    assert error is None
    assert name == (names[0] if names else None)


def test_select_processing_unit_application_fails_without_answer(monkeypatch):
    _set_pua_names(monkeypatch, ["PUA_1", "PUA_2"])

    async def choose(_names):
        return None

    name, error = asyncio.run(model_svc.select_processing_unit_application(choose))

    assert name is None
    assert json.loads(error)["success"] is False


def test_processing_unit_application_elicitation_offers_existing_names():
    from sources.tools.model_topology import _choose_processing_unit_application

    class _Ctx:
        async def elicit(self, message, schema):
            assert schema.model_json_schema()["properties"]["processing_unit_application"][
                "enum"
            ] == ["PUA_1", "PUA_2"]
            return SimpleNamespace(
                action="accept", data=schema(processing_unit_application="PUA_1")
            )

    assert asyncio.run(_choose_processing_unit_application(_Ctx(), ["PUA_1", "PUA_2"])) == "PUA_1"


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


# ── Model port → model port connections (COM layer) ──────────────────────────

_GROUP_PROPS = ["Name"]
_REFUSAL = "ConnectObjects\r\nConnectObjects: Cannot connect \r\n; HResult; "


class _ComError(Exception):
    """Shape of the pywintypes.com_error ConfigurationDesk raises from ConnectObjects."""

    def __init__(self, description):
        self.excepinfo = (0, "ConfigurationDeskAutomationCore", description, None, 0, -1)
        super().__init__(-2147352567, "Exception occurred.", self.excepinfo, None)


class _Port(_TopologyNode):
    def __init__(self, name):
        super().__init__(name, _PORT_PROPS)
        self.ConnectedObjects = []


def _xml_item(name, context="", effect="", prop="", value="", children=()):
    columns = "".join(
        f'<Column Name="{column}" Value="{text}" />'
        for column, text in (
            ("Name", name),
            ("Context", context),
            ("Property", prop),
            ("Value", value),
            ("Suggested Values", ""),
            ("Effect", effect),
        )
    )
    return f"<Item>{columns}{''.join(children)}</Item>"


class _FakeConnectApplication:
    """ActiveApplication + Algorithms fake: links ports and exports conflicts as XML."""

    def __init__(self, models, block_of, refuse=False):
        self.models = models
        self.block_of = block_of
        self.refuse = refuse
        self.connect_calls = 0
        self.links = []

    def ConnectObjects(self, first, second):
        self.connect_calls += 1
        if self.refuse:
            raise _ComError(_REFUSAL)
        first.ConnectedObjects.append(second)
        second.ConnectedObjects.append(first)
        for port in (first, second):
            self.block_of[id(port)].IsInApplication = True
        self.links.append((first, second))

    def ExportConflictsToXML(self, path, infos, group):
        assert (infos, group) == ([], "")
        conflicts = [
            _xml_item(
                "No application process",
                context="Application process",
                effect="Abort build",
                children=[_xml_item("ProcessingUnitApplication")],
            )
        ]
        for first, second in self.links:
            model_of = {id(p): m for m, ports in self.models.items() for p in ports}
            if model_of[id(first)] == model_of[id(second)]:
                ports = [
                    _xml_item(p.Name, prop="Model", value=model_of[id(p)]) for p in (first, second)
                ]
                conflicts.append(
                    _xml_item(
                        "Invalid connection between data port blocks of same model",
                        context="Model port mapping",
                        effect="Generate no code",
                        children=[
                            _xml_item(
                                f"Mapping line ({first.Name} - {second.Name})", children=ports
                            )
                        ],
                    )
                )
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(f"<Top>{_xml_item('Model', children=conflicts)}</Top>")


def _connect_fixture(refuse=False):
    """M1: nested port groups and two same-level 'FIR' blocks; M2: 'In' at two levels."""
    speed, gear = _Port("Speed"), _Port("Gear")
    fir_in, fir_out = _Port("Input"), _Port("Output")
    m2_root_in, m2_sub_in = _Port("data1"), _Port("data1")

    def block(name, children):
        return _TopologyNode(name, _BLOCK_PROPS, children)

    out_block = block(
        "Out",
        [_TopologyNode("Bus", _GROUP_PROPS, [_TopologyNode("Inner", _GROUP_PROPS, [speed, gear])])],
    )
    fir_in_block, fir_out_block = block("FIR", [fir_in]), block("FIR", [fir_out])
    m2_root_block, m2_sub_block = block("In", [m2_root_in]), block("In", [m2_sub_in])
    m2_root_block.IsInApplication = True
    m1 = _TopologyNode("M1", ["Name", "Source type"], [out_block, fir_in_block, fir_out_block])
    m2 = _TopologyNode(
        "M2",
        ["Name", "Source type"],
        [m2_root_block, _TopologyNode("Sub", _SUBSYSTEM_PROPS, [m2_sub_block])],
    )
    block_of = {
        id(speed): out_block,
        id(gear): out_block,
        id(fir_in): fir_in_block,
        id(fir_out): fir_out_block,
        id(m2_root_in): m2_root_block,
        id(m2_sub_in): m2_sub_block,
    }
    models = {"M1": [speed, gear, fir_in, fir_out], "M2": [m2_root_in, m2_sub_in]}
    app = _FakeConnectApplication(models, block_of, refuse=refuse)
    conn = SimpleNamespace(
        model_topology=_TopologyNode("mt", [], [m1, m2]), active=app, algorithms=app
    )
    ports = SimpleNamespace(speed=speed, fir_in=fir_in, fir_out=fir_out, m2_root_in=m2_root_in)
    return conn, app, ports


def test_connect_nested_port_to_other_model_without_conflicts():
    conn, _app, ports = _connect_fixture()

    result = model_topology_com.connect_model_port_to_model_port(
        conn, "M1", "Out", "Bus/Inner/Speed", "M2", "M2/In", "data1"
    )

    assert result["connected"] is True
    assert result["new_conflicts"] == []
    assert result["source"] == {
        "model_name": "M1",
        "port_block_path": "M1/Out",
        "port_path": "Bus/Inner/Speed",
        "port_name": "Speed",
        "full_path": "M1/Out/Bus/Inner/Speed",
    }
    assert ports.speed.ConnectedObjects == [ports.m2_root_in]
    assert result["blocks_added_to_signal_chain"] == ["M1/Out"]


def test_connect_same_model_reports_only_the_new_link_conflict():
    conn, _app, _ports = _connect_fixture()

    result = model_topology_com.connect_model_port_to_model_port(
        conn, "M1", "FIR", "Output", "M1", "FIR", "Input"
    )

    assert result["connected"] is True
    [conflict] = result["new_conflicts"]
    assert conflict["context_set"] == "Model"
    assert conflict["name"] == "Invalid connection between data port blocks of same model"
    assert conflict["context"] == "Model port mapping"
    assert conflict["effect"] == "Generate no code"
    assert result["target"]["port_block_path"] == "M1/FIR"


def test_connect_returns_configurationdesk_refusal_unchanged():
    conn, app, ports = _connect_fixture(refuse=True)

    result = model_topology_com.connect_model_port_to_model_port(
        conn, "M1", "FIR", "Input", "M1", "FIR", "Input"
    )

    assert result["reason"] == "connect_refused"
    assert result["configurationdesk_message"] == _REFUSAL
    assert app.connect_calls == 1
    assert ports.fir_in.ConnectedObjects == []


def test_connect_preserves_created_link_when_second_conflict_export_fails(monkeypatch):
    conn, app, ports = _connect_fixture()
    export_calls = []

    def export_conflicts(_connection):
        export_calls.append(True)
        if len(export_calls) == 2:
            raise _ComError("Conflict export failed")
        return []

    monkeypatch.setattr(model_topology_com, "export_conflict_tree", export_conflicts)

    result = model_topology_com.connect_model_port_to_model_port(
        conn, "M1", "Out", "Bus/Inner/Speed", "M2", "M2/In", "data1"
    )

    assert result["connected"] is True
    assert result["conflicts_read_error"] == "Conflict export failed"
    assert result["blocks_added_to_signal_chain"] == ["M1/Out"]
    assert "error" not in result
    assert "new_conflicts" not in result
    assert ports.speed.ConnectedObjects == [ports.m2_root_in]
    assert app.connect_calls == 1
    assert len(export_calls) == 2


@pytest.mark.parametrize("verified", [True, False])
def test_connect_service_reports_conflict_read_failure_without_connection_error(
    fake_bridge, monkeypatch, verified
):
    from tests._fake_bridge import dispatch_returns

    result = dispatch_returns()["connect_model_port_to_model_port"](
        "demosmd_io", "Out1", "Speed", "EngineAndBodyECUs_64-bit", "In1", "data1"
    )
    del result["new_conflicts"]
    result.update(connected=verified, conflicts_read_error="Conflict export failed")

    async def dispatch_result(*_args, **_kwargs):
        return result

    monkeypatch.setattr(model_svc, "dispatch", dispatch_result)

    payload = run_ok(
        model_svc.connect_model_port_to_model_port(
            "demosmd_io", "Out1", "Speed", "EngineAndBodyECUs_64-bit", "In1", "data1"
        )
    )

    assert payload["verified"] is verified
    assert payload["status"] == "unknown"
    assert payload["conflicts_read_error"] == "Conflict export failed"
    assert "conflicts could not be read" in payload["message"]
    assert "Do not repeat the connection" in payload["note"]
    assert payload["source"] == result["source"]
    assert payload["target"] == result["target"]


@pytest.mark.parametrize(
    "failure",
    [
        _ComError("The object invoked has disconnected from its clients."),
        RuntimeError("Unexpected connection failure"),
    ],
)
def test_connect_propagates_non_refusal_exceptions(monkeypatch, failure):
    conn, app, ports = _connect_fixture()

    def fail_connect(_first, _second):
        raise failure

    monkeypatch.setattr(app, "ConnectObjects", fail_connect)
    monkeypatch.setattr(model_topology_com, "export_conflict_tree", lambda _conn: [])

    with pytest.raises(type(failure)) as raised:
        model_topology_com.connect_model_port_to_model_port(
            conn, "M1", "Out", "Bus/Inner/Speed", "M2", "M2/In", "data1"
        )

    assert raised.value is failure
    assert ports.speed.ConnectedObjects == []


def test_connect_service_uses_normal_error_handling_for_non_refusal(fake_bridge, monkeypatch):
    async def fail_dispatch(*_args, **_kwargs):
        raise _ComError("The object invoked has disconnected from its clients.")

    monkeypatch.setattr(model_svc, "dispatch", fail_dispatch)

    payload = run_raw(
        model_svc.connect_model_port_to_model_port(
            "demosmd_io", "Out1", "Speed", "EngineAndBodyECUs_64-bit", "In1", "data1"
        )
    )

    assert payload["success"] is False
    assert payload["error_code"] != "MAPPING_REFUSED"
    assert "disconnected from its clients" in payload["error"]
    assert "configurationdesk_message" not in payload


@pytest.mark.parametrize("port_path", ["Bus/Missing", "Bus/Inner", "Bus"])
def test_connect_rejects_port_path_that_is_not_a_model_port(port_path):
    conn, app, _ports = _connect_fixture()

    result = model_topology_com.connect_model_port_to_model_port(
        conn, "M1", "Out", port_path, "M2", "M2/In", "data1"
    )

    assert result["reason"] == "model_port_not_found"
    assert result["endpoint"] == "source"
    assert result["available_port_paths"] == ["Bus/Inner/Speed", "Bus/Inner/Gear"]
    assert app.connect_calls == 0


def test_connect_rejects_block_name_shared_across_hierarchy_levels():
    conn, app, _ports = _connect_fixture()

    result = model_topology_com.connect_model_port_to_model_port(
        conn, "M1", "Out", "Bus/Inner/Speed", "M2", "In", "data1"
    )

    assert result["reason"] == "ambiguous_model_port_block_hierarchy"
    assert result["endpoint"] == "target"
    assert result["candidates"] == ["M2/In", "M2/Sub/In"]
    assert app.connect_calls == 0


def test_list_model_ports_adds_leaf_ports_nested_in_port_groups():
    conn, _app, _ports = _connect_fixture()

    result = model_topology_com.list_model_ports(conn, "M1", "Out")

    assert [port["name"] for port in result["ports"]] == ["Bus"]
    assert result["count"] == 1
    assert [
        (port["port_path"], port["full_path"], port["port_block_path"])
        for port in result["leaf_ports"]
    ] == [
        ("Bus/Inner/Speed", "M1/Out/Bus/Inner/Speed", "M1/Out"),
        ("Bus/Inner/Gear", "M1/Out/Bus/Inner/Gear", "M1/Out"),
    ]
