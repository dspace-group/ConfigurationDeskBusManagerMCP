# -*- coding: utf-8 -*-
"""Domain: model topology tools (sources/tools/model_topology.py)."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from configurationdesk_com_bridge.domains import model_topology_com
from sources.services import model_topology_service as model_svc

from tests.domains.conftest import run_ok

COVERS = (
    "add_model",
    "replace_model",
    "remove_model",
    "analyze_models",
    "create_application_process",
    "list_models",
    "add_model_to_signal_chain",
    "add_model_port_to_signal_chain",
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


def test_add_model_port_to_signal_chain(fake_bridge):
    run_ok(model_svc.add_model_port_to_signal_chain("demosmd_io", "In1"))


def test_list_model_ports(fake_bridge):
    payload = run_ok(model_svc.list_model_ports("demosmd_io"))
    assert payload["count"] == 2


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
