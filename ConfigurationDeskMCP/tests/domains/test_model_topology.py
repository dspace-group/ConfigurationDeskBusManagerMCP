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
)


def _model_files(tmp_path, *names):
    paths = []
    for name in names:
        path = tmp_path / name
        path.write_bytes(b"")
        paths.append(str(path))
    return paths


def _record_dispatch(monkeypatch, *, pua_names=("PUA_1",), process_names=("AppProcess",)):
    """Route dispatch through the fake bridge and record ``(name, args)`` of every call."""
    from tests import _fake_bridge

    returns = _fake_bridge.dispatch_returns()
    returns["list_processing_unit_application_names"] = list(pua_names)
    returns["list_application_process_names"] = list(process_names)
    calls = []

    async def fake_dispatch(fn, *args, **kwargs):
        calls.append((fn.__name__, args[1:]))
        handler = returns[fn.__name__]
        return handler(*args[1:]) if callable(handler) else handler

    monkeypatch.setattr(model_svc, "dispatch", fake_dispatch)
    monkeypatch.setattr(model_svc, "get_connection", lambda: SimpleNamespace())
    return calls


def _call(calls, name):
    return [args for called, args in calls if called == name]


def test_add_model(fake_bridge, tmp_path):
    paths = _model_files(tmp_path, "CentralGatewayECU_64-bit.sic")
    payload = run_ok(model_svc.add_models(paths))
    assert "CentralGatewayECU_64-bit" in payload["added"]


def test_add_models_per_model_decides_analysis_by_file_type(monkeypatch, tmp_path):
    calls = _record_dispatch(monkeypatch)
    paths = _model_files(tmp_path, "Plant.slx", "Legacy.MDL", "Restbus.sic", "Bus.bsc", "Ecu.fmu")

    payload = run_ok(model_svc.add_models(paths, "per_model"))

    (args,) = _call(calls, "add_models")
    models, mode, shared_name = args
    assert [analyze for _, analyze in models] == [True, True, False, False, False]
    assert mode == model_topology_com.AP_ONE_FOR_EACH
    assert shared_name is None
    assert payload["verified"] is True
    assert payload["assignments"]["Plant"] == ["Plant"]
    assert payload["processing_unit_application"] == "PUA_1"


def test_add_models_none_creates_no_application_process(monkeypatch, tmp_path):
    calls = _record_dispatch(monkeypatch, pua_names=["PUA_1", "PUA_2"])
    paths = _model_files(tmp_path, "A.fmu", "B.fmu")

    payload = run_ok(model_svc.add_models(paths, "none"))

    (args,) = _call(calls, "add_models")
    assert args[1] == model_topology_com.AP_NONE
    assert not _call(calls, "list_processing_unit_application_names")
    assert payload["created_processes"] == []
    assert payload["added"] == ["A", "B"]


def test_add_models_new_shared_names_the_application_process(monkeypatch, tmp_path):
    calls = _record_dispatch(monkeypatch)
    paths = _model_files(tmp_path, "A.fmu", "B.slx")

    payload = run_ok(model_svc.add_models(paths, "new_shared", application_process="Shared_AP"))

    (args,) = _call(calls, "add_models")
    assert args[1:] == (model_topology_com.AP_ONE_FOR_ALL, "Shared_AP")
    assert payload["created_processes"] == ["Shared_AP"]
    assert payload["assignments"] == {"A": ["Shared_AP"], "B": ["Shared_AP"]}


def test_add_models_per_model_with_several_processing_unit_applications(monkeypatch, tmp_path):
    calls = _record_dispatch(monkeypatch, pua_names=["PUA_1", "PUA_2"])
    paths = _model_files(tmp_path, "A.fmu", "B.fmu")
    offered = []

    async def choose(names):
        offered.extend(names)
        return "pua_2"

    payload = run_ok(
        model_svc.add_models(paths, "per_model", choose_processing_unit_application=choose)
    )

    assert offered == ["PUA_1", "PUA_2"]
    assert _call(calls, "add_models")[0][1] == model_topology_com.AP_NONE
    assert _call(calls, "create_preconfigured_application_processes") == [(["A", "B"], "PUA_2")]
    assert payload["multiple_processing_unit_applications_workaround"] is True
    assert payload["created_processes"] == ["A", "B"]
    assert payload["processing_unit_application"] == "PUA_2"


def test_add_models_new_shared_with_several_processing_unit_applications(monkeypatch, tmp_path):
    calls = _record_dispatch(monkeypatch, pua_names=["PUA_1", "PUA_2"])
    paths = _model_files(tmp_path, "A.fmu", "B.fmu")

    payload = run_ok(
        model_svc.add_models(
            paths,
            "new_shared",
            application_process="Shared_AP",
            processing_unit_application="PUA_1",
        )
    )

    assert _call(calls, "create_application_process") == [("Shared_AP", [], False, "PUA_1")]
    (args,) = _call(calls, "add_models_to_application_process")
    assert args[1:] == ("Shared_AP", True)
    assert not _call(calls, "add_models")
    assert payload["optimized"] is True
    assert payload["created_processes"] == ["Shared_AP"]


def test_add_models_without_processing_unit_application_choice_adds_nothing(monkeypatch, tmp_path):
    calls = _record_dispatch(monkeypatch, pua_names=["PUA_1", "PUA_2"])
    paths = _model_files(tmp_path, "A.fmu")

    async def choose(_names):
        return None

    payload = json.loads(
        asyncio.run(
            model_svc.add_models(paths, "new_shared", choose_processing_unit_application=choose)
        )
    )

    assert payload["success"] is False
    assert "processing_unit_application" in payload["next_action"]
    assert not _call(calls, "add_models")
    assert not _call(calls, "create_application_process")


def test_add_models_existing_uses_only_application_process(monkeypatch, tmp_path):
    calls = _record_dispatch(monkeypatch, process_names=["Only_AP"])
    paths = _model_files(tmp_path, "A.fmu", "B.slx")

    async def choose(_names):
        raise AssertionError("user must not be asked")

    payload = run_ok(
        model_svc.add_models(
            paths, "existing", optimize_configuration=False, choose_application_process=choose
        )
    )

    (args,) = _call(calls, "add_models_to_application_process")
    models, target, optimize = args
    assert [analyze for _, analyze in models] == [False, True]
    assert (target, optimize) == ("Only_AP", False)
    assert payload["assignments"] == {"A": ["Only_AP"], "B": ["Only_AP"]}


def test_add_models_existing_asks_user_when_several(monkeypatch, tmp_path):
    calls = _record_dispatch(monkeypatch, process_names=["AP_1", "AP_2"])
    paths = _model_files(tmp_path, "A.fmu")
    offered = []

    async def choose(names):
        offered.extend(names)
        return "AP_2"

    run_ok(model_svc.add_models(paths, "existing", choose_application_process=choose))

    assert offered == ["AP_1", "AP_2"]
    assert _call(calls, "add_models_to_application_process")[0][1:] == ("AP_2", True)


def test_add_models_existing_matches_given_name_case_insensitively(monkeypatch, tmp_path):
    calls = _record_dispatch(monkeypatch, process_names=["AP_1", "AP_2"])
    paths = _model_files(tmp_path, "A.fmu")

    run_ok(model_svc.add_models(paths, "existing", application_process="ap_1"))

    assert _call(calls, "add_models_to_application_process")[0][1] == "AP_1"


@pytest.mark.parametrize(
    ("process_names", "requested", "expected"),
    [
        ([], None, "no application process"),
        (["AP_1", "AP_2"], None, "not selected"),
        (["AP_1"], "Missing_AP", "not found"),
    ],
)
def test_add_models_existing_errors(monkeypatch, tmp_path, process_names, requested, expected):
    calls = _record_dispatch(monkeypatch, process_names=process_names)
    paths = _model_files(tmp_path, "A.fmu")

    payload = json.loads(
        asyncio.run(model_svc.add_models(paths, "existing", application_process=requested))
    )

    assert payload["success"] is False
    assert expected in payload["error"]
    assert not _call(calls, "add_models_to_application_process")


def test_add_models_rejects_missing_and_unsupported_files(monkeypatch, tmp_path):
    calls = _record_dispatch(monkeypatch)
    existing = _model_files(tmp_path, "A.fmu", "notes.txt")

    missing = json.loads(
        asyncio.run(model_svc.add_models([existing[0], str(tmp_path / "Missing.slx")]))
    )
    unsupported = json.loads(asyncio.run(model_svc.add_models(existing)))

    assert missing["success"] is False and "Missing.slx" in missing["error"]
    assert unsupported["success"] is False and "notes.txt" in unsupported["error"]
    assert calls == []


def test_add_models_reports_partial_result_as_unverified(monkeypatch, tmp_path):
    calls = _record_dispatch(monkeypatch, process_names=["AP_1"])
    paths = _model_files(tmp_path, "A.fmu", "B.fmu")

    async def partial(fn, *args, **kwargs):
        calls.append((fn.__name__, args[1:]))
        if fn.__name__ == "list_application_process_names":
            return ["AP_1"]
        return {
            "application_process": "AP_1",
            "added": ["A"],
            "failed": [{"path": paths[1], "detail": "Model already present."}],
            "verified": False,
            "all_models": ["A"],
            "assignments": {"A": ["AP_1"]},
            "optimized": True,
            "optimize_detail": "",
        }

    monkeypatch.setattr(model_svc, "dispatch", partial)

    payload = json.loads(asyncio.run(model_svc.add_models(paths, "existing")))

    assert payload["success"] is True
    assert payload["verified"] is False
    assert "only 1 of 2" in payload["message"]
    assert payload["failed"][0]["detail"] == "Model already present."


def test_add_model_input_validation():
    from pydantic import ValidationError

    from sources.models.model_topology_inputs import AddModelInput

    assert AddModelInput(paths="C:/m.fmu").paths == ["C:/m.fmu"]
    assert AddModelInput(paths=["C:/m.fmu"]).application_process_mode == "per_model"
    with pytest.raises(ValidationError):
        AddModelInput(paths=[])
    with pytest.raises(ValidationError):
        AddModelInput(paths=["C:/m.fmu"], application_process="AP_1")
    with pytest.raises(ValidationError):
        AddModelInput(
            paths=["C:/m.fmu"], application_process_mode="existing", processing_unit_application="P"
        )
    with pytest.raises(ValidationError):
        AddModelInput(paths=["C:/m.fmu"], application_process_mode="shared")


def test_application_process_elicitation_offers_existing_names():
    from sources.tools.model_topology import _choose_application_process

    class _Ctx:
        async def elicit(self, message, schema):
            assert schema.model_json_schema()["properties"]["application_process"]["enum"] == [
                "AP_1",
                "AP_2",
            ]
            return SimpleNamespace(action="accept", data=schema(application_process="AP_2"))

    assert asyncio.run(_choose_application_process(_Ctx(), ["AP_1", "AP_2"])) == "AP_2"
    assert asyncio.run(_choose_application_process(None, ["AP_1", "AP_2"])) is None


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
