# -*- coding: utf-8 -*-
"""Domain: model topology tools (sources/tools/model_topology.py)."""

from __future__ import annotations

from types import SimpleNamespace

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
    run_ok(model_svc.create_application_process())


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

    pu_application, detail = model_topology_com._resolve_processing_unit_application(
        SimpleNamespace(),
        _FakeRelation(),
    )

    assert pu_application is processing_unit
    assert detail == ""


def test_resolve_processing_unit_application_still_fails_without_processing_unit():
    exec_app = SimpleNamespace(Name="RestbusApp", Roles=["ExecutableApplication"])

    class _FakeRelation:
        def GetTopNodes(self):
            return _FakeCollection([exec_app])

        def GetElements(self, _parent):
            return _FakeCollection([])

    pu_application, detail = model_topology_com._resolve_processing_unit_application(
        SimpleNamespace(),
        _FakeRelation(),
    )

    assert pu_application is None
    assert (
        "No ProcessingUnitApplication is available under the active executable application"
        in detail
    )
