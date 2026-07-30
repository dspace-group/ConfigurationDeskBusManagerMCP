# -*- coding: utf-8 -*-
"""Regression tests for runtime guard and precondition state checks."""

import asyncio
import json
from types import SimpleNamespace

import pytest

from configurationdesk_com_bridge.errors import BridgeConnectionError
from configurationdesk_com_bridge.domains import (
    application_com,
    bus_config_com,
    hardware_com,
    model_topology_com,
    verify_com,
)
from sources.server import preconditions
from sources.services import _workflow_readiness as workflow_readiness
from sources.services import _observations as observations
from sources.services import (
    build_service,
    bus_access_service,
    bus_config_service,
    model_topology_service,
    project_service,
)


class _LegacyActiveApplication:
    def __init__(self, name: str):
        self.Application = SimpleNamespace(Name=name)

    @property
    def Name(self):
        raise AttributeError("Legacy COM interface")


def test_get_status_uses_modern_active_application_name():
    conn = SimpleNamespace(
        app=SimpleNamespace(
            ActiveProject=SimpleNamespace(Name="ProjectA"),
            ActiveProjectRoot=SimpleNamespace(PathName="D:/Projects"),
            ActiveApplication=SimpleNamespace(
                Name="ModernApp",
                Application=SimpleNamespace(Name="LegacyApp"),
            ),
        )
    )

    status = application_com.get_status(conn)

    assert status["project"] == "ProjectA"
    assert status["project_name"] == "ProjectA"
    assert status["application"] == "ModernApp"
    assert status["application_name"] == "ModernApp"


def test_get_status_falls_back_to_legacy_active_application_name():
    conn = SimpleNamespace(
        app=SimpleNamespace(
            ActiveProject=SimpleNamespace(Name="ProjectA"),
            ActiveProjectRoot=SimpleNamespace(PathName="D:/Projects"),
            ActiveApplication=_LegacyActiveApplication("LegacyApp"),
        )
    )

    status = application_com.get_status(conn)

    assert status["application"] == "LegacyApp"
    assert status["application_name"] == "LegacyApp"


def test_preconditions_use_status_contract_and_list_configs(monkeypatch):
    conn = SimpleNamespace(is_connected=True)

    async def fake_dispatch(fn, passed_conn, *args, **kwargs):
        assert passed_conn is conn
        if fn is application_com.get_status:
            return {
                "project": "ProjectA",
                "application": "AppA",
            }
        if fn is bus_config_com.list_configs:
            return ["BusConfigA"]
        raise AssertionError(f"Unexpected dispatch target: {fn}")

    monkeypatch.setattr(preconditions, "logger", preconditions.logger)
    monkeypatch.setattr("configurationdesk_com_bridge.get_connection", lambda: conn)
    monkeypatch.setattr("configurationdesk_com_bridge.dispatch", fake_dispatch)

    project_ok, _ = asyncio.run(preconditions._check_project())
    application_ok, _ = asyncio.run(preconditions._check_application())
    bus_config_ok, _ = asyncio.run(preconditions._check_bus_config())

    assert project_ok is True
    assert application_ok is True
    assert bus_config_ok is True


def test_preconditions_can_check_model_and_application_process(monkeypatch):
    conn = SimpleNamespace(is_connected=True)

    async def fake_dispatch(fn, passed_conn, *args, **kwargs):
        assert passed_conn is conn
        if fn is model_topology_com.list_models:
            return ["ModelA"]
        if fn is verify_com.list_application_process_names:
            return ["AppProcessA"]
        raise AssertionError(f"Unexpected dispatch target: {fn}")

    monkeypatch.setattr("configurationdesk_com_bridge.get_connection", lambda: conn)
    monkeypatch.setattr("configurationdesk_com_bridge.dispatch", fake_dispatch)

    model_ok, _ = asyncio.run(preconditions._check_model())
    process_ok, _ = asyncio.run(preconditions._check_application_process())

    assert model_ok is True
    assert process_ok is True


def test_preconditions_can_check_hardware_topology(monkeypatch):
    conn = SimpleNamespace(is_connected=True)

    async def fake_dispatch(fn, passed_conn, *args, **kwargs):
        assert passed_conn is conn
        if fn is hardware_com.list_hardware_names:
            return ["SCALEXIO_Rack"]
        raise AssertionError(f"Unexpected dispatch target: {fn}")

    monkeypatch.setattr("configurationdesk_com_bridge.get_connection", lambda: conn)
    monkeypatch.setattr("configurationdesk_com_bridge.dispatch", fake_dispatch)

    hardware_ok, _ = asyncio.run(preconditions._check_hardware_topology())

    assert hardware_ok is True


def test_preconditions_propagate_bridge_errors(monkeypatch):
    conn = SimpleNamespace(is_connected=True)

    async def fake_dispatch(fn, passed_conn, *args, **kwargs):
        assert passed_conn is conn
        raise BridgeConnectionError("lost")

    @preconditions.with_preconditions("project")
    async def guarded() -> str:
        raise AssertionError("guarded body should not run")

    monkeypatch.setattr("configurationdesk_com_bridge.get_connection", lambda: conn)
    monkeypatch.setattr("configurationdesk_com_bridge.dispatch", fake_dispatch)

    payload = json.loads(asyncio.run(guarded()))

    assert payload["success"] is False
    assert payload["error_code"] == "COM_DISCONNECTED"


def test_preconditions_report_unexpected_probe_failures(monkeypatch):
    conn = SimpleNamespace(is_connected=True)

    async def fake_dispatch(fn, passed_conn, *args, **kwargs):
        assert passed_conn is conn
        raise ValueError("boom")

    @preconditions.with_preconditions("project")
    async def guarded() -> str:
        raise AssertionError("guarded body should not run")

    monkeypatch.setattr("configurationdesk_com_bridge.get_connection", lambda: conn)
    monkeypatch.setattr("configurationdesk_com_bridge.dispatch", fake_dispatch)

    payload = json.loads(asyncio.run(guarded()))

    assert payload["success"] is False
    assert payload["error_code"] == "PRECONDITION_CHECK_FAILED"


def test_create_application_process_can_run_without_model(monkeypatch):
    conn = SimpleNamespace(is_connected=True)

    async def fake_dispatch(fn, passed_conn, *args, **kwargs):
        assert passed_conn is conn
        if fn is model_topology_com.create_application_process:
            return {
                "verified": True,
                "process_name": "AppProcess",
                "default_task_set": True,
                "default_task_property": "ProvideDefaultTask",
                "default_task_name": "Periodic Task 1",
                "created_processes": ["AppProcess"],
            }
        raise AssertionError(f"Unexpected dispatch target: {fn}")

    monkeypatch.setattr(model_topology_service, "get_connection", lambda: conn)
    monkeypatch.setattr(model_topology_service, "dispatch", fake_dispatch)

    payload = json.loads(asyncio.run(model_topology_service.create_application_process()))

    assert payload["success"] is True


def test_auto_connect_io_function_blocks_requires_application_process(monkeypatch):
    conn = SimpleNamespace(is_connected=True)

    async def fake_dispatch(fn, passed_conn, *args, **kwargs):
        assert passed_conn is conn
        if fn is model_topology_com.list_models:
            return ["ModelA"]
        if fn is verify_com.list_application_process_names:
            return []
        raise AssertionError(f"Unexpected dispatch target: {fn}")

    monkeypatch.setattr(bus_access_service, "get_connection", lambda: conn)
    monkeypatch.setattr(bus_access_service, "dispatch", fake_dispatch)
    monkeypatch.setattr(observations, "dispatch", fake_dispatch)

    payload = json.loads(
        asyncio.run(bus_access_service.auto_connect_matching_io_function_blocks_to_model_ports())
    )

    assert payload["success"] is False
    assert payload["error_code"] == "BRIDGE_PRECONDITION"


def test_assign_channel_set_requires_hardware_topology(monkeypatch):
    conn = SimpleNamespace(is_connected=True)

    async def fake_dispatch(fn, passed_conn, *args, **kwargs):
        assert passed_conn is conn
        if fn is hardware_com.list_hardware_names:
            return []
        raise AssertionError(f"Unexpected dispatch target: {fn}")

    monkeypatch.setattr(bus_access_service, "get_connection", lambda: conn)
    monkeypatch.setattr(bus_access_service, "dispatch", fake_dispatch)
    monkeypatch.setattr(observations, "dispatch", fake_dispatch)

    payload = json.loads(asyncio.run(bus_access_service.assign_channel_set("CAN_1", 0, "CAN")))

    assert payload["success"] is False
    assert payload["error_code"] == "BRIDGE_PRECONDITION"


def test_build_with_download_requires_hardware_topology(monkeypatch):
    conn = SimpleNamespace(is_connected=True)

    async def fake_dispatch(fn, passed_conn, *args, **kwargs):
        assert passed_conn is conn
        if fn is hardware_com.list_hardware_names:
            return []
        raise AssertionError(f"Unexpected dispatch target: {fn}")

    monkeypatch.setattr(build_service, "get_connection", lambda: conn)
    monkeypatch.setattr(build_service, "dispatch", fake_dispatch)
    monkeypatch.setattr(observations, "dispatch", fake_dispatch)

    payload = json.loads(
        asyncio.run(build_service.build_application(download=True, start=False, unload=True))
    )

    assert payload["success"] is False
    assert payload["error_code"] == "BRIDGE_PRECONDITION"


def test_canceled_build_requires_user_decision_before_rerun(monkeypatch):
    conn = SimpleNamespace(is_connected=True)

    async def fake_dispatch(fn, passed_conn, *args, **kwargs):
        assert fn is build_service.build_com.build_application
        assert passed_conn is conn
        return {"success": False, "canceled": True}

    monkeypatch.setattr(build_service, "get_connection", lambda: conn)
    monkeypatch.setattr(build_service, "dispatch", fake_dispatch)

    payload = json.loads(
        asyncio.run(build_service.build_application(download=False, start=False, unload=True))
    )

    assert payload["success"] is False
    assert payload["retryable"] is False
    assert "Do NOT retry automatically" in payload["next_action"]
    assert "user chooses" in payload["next_action"]


def test_observational_dispatch_is_bounded_and_does_not_reconnect(monkeypatch):
    conn = SimpleNamespace(is_connected=True)
    calls = []

    async def fake_dispatch(fn, passed_conn, *args, **kwargs):
        assert passed_conn is conn
        calls.append((fn, args, kwargs))
        if fn is project_service.project_com.list_projects:
            return ["DemoProject"]
        if fn is model_topology_com.list_models:
            return ["ModelA"]
        raise AssertionError(f"Unexpected dispatch target: {fn}")

    monkeypatch.setattr(project_service, "get_connection", lambda: conn)
    monkeypatch.setattr(observations, "dispatch", fake_dispatch)

    project_payload = json.loads(asyncio.run(project_service.list_projects()))
    ready_models = asyncio.run(workflow_readiness.require_model_ready(conn))

    assert project_payload["success"] is True
    assert ready_models == ["ModelA"]
    assert [call[0] for call in calls] == [
        project_service.project_com.list_projects,
        model_topology_com.list_models,
    ]
    for _, _, kwargs in calls:
        assert kwargs == {"timeout_ms": 5_000, "reconnect": False}
