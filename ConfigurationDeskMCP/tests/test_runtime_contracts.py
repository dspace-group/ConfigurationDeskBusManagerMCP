# -*- coding: utf-8 -*-
"""Regression tests for runtime settings, error contracts, and reconnect handling."""

import asyncio
import concurrent.futures
import json
from types import SimpleNamespace

import pytest

import configurationdesk_com_bridge as bridge
from configurationdesk_com_bridge.domains import app_management_com
from configurationdesk_com_bridge.connection import ConnectionState
from configurationdesk_com_bridge.errors import BridgeConnectionError, BridgeTimeoutError
from sources.services import application_service
from sources.services import _observations as observations
from sources.tools._responses import error_response


def test_error_response_includes_contract_fields():
    payload = json.loads(error_response("boom"))

    assert payload["success"] is False
    assert payload["error"] == "boom"
    assert payload["error_code"] == "BRIDGE_UNKNOWN"
    assert payload["retryable"] is False
    assert payload["recovery_hint"]
    assert payload["next_action"]


def test_guarded_call_propagates_bridge_reconnect_error():
    class _BrokenConnection:
        def health_check(self):
            return False

        def reconnect(self):
            raise BridgeConnectionError("lost")

    with pytest.raises(BridgeConnectionError, match="lost"):
        bridge._guarded_call(lambda connection: connection, (_BrokenConnection(),))


def test_dispatch_without_reconnect_reports_unhealthy_connection(monkeypatch):
    class _FakeStaThread:
        def submit(self, function, *args):
            future = concurrent.futures.Future()
            try:
                future.set_result(function(*args))
            except Exception as exc:
                future.set_exception(exc)
            return future

    class _BrokenConnection:
        def __init__(self):
            self.reconnect_calls = 0

        def health_check(self):
            return False

        def reconnect(self):
            self.reconnect_calls += 1
            return True

    connection = _BrokenConnection()
    monkeypatch.setattr(bridge._sta, "get_sta_thread", lambda: _FakeStaThread())

    with pytest.raises(BridgeConnectionError, match="not healthy"):
        asyncio.run(
            bridge.dispatch(
                lambda passed_connection: passed_connection, connection, reconnect=False
            )
        )

    assert connection.reconnect_calls == 0


def test_dispatch_honors_explicit_observation_timeout(monkeypatch):
    class _HangingStaThread:
        def submit(self, function, *args):
            return concurrent.futures.Future()

    monkeypatch.setattr(bridge._sta, "get_sta_thread", lambda: _HangingStaThread())

    with pytest.raises(BridgeTimeoutError, match="10 ms"):
        asyncio.run(bridge.dispatch(lambda: None, timeout_ms=10))


def test_startup_applies_runtime_defaults(monkeypatch):
    created = {}

    class _FakeConnection:
        def __init__(self, *, launch_timeout_ms: int, reconnect_attempts: int):
            created["launch_timeout_ms"] = launch_timeout_ms
            created["reconnect_attempts"] = reconnect_attempts

    monkeypatch.setattr(bridge._sta, "startup", lambda: None)
    monkeypatch.setattr(bridge, "ConfigurationDeskConnection", _FakeConnection)
    monkeypatch.setattr(bridge, "_connection", None)

    asyncio.run(
        bridge.startup(
            default_timeout_ms=4321,
            launch_timeout_ms=8765,
            reconnect_attempts=4,
        )
    )

    assert bridge._resolve_timeout_ms(None) == 4321
    assert created == {
        "launch_timeout_ms": 8765,
        "reconnect_attempts": 4,
    }


def test_shutdown_detaches_without_disconnect(monkeypatch):
    called = {"detach": 0, "disconnect": 0, "sta_shutdown": 0}

    class _FakeConnection:
        def detach(self):
            called["detach"] += 1
            return True

        def disconnect(self, save=True):
            called["disconnect"] += 1
            return True

    class _FakeStaThread:
        def submit(self, function, *args):
            future = concurrent.futures.Future()
            try:
                future.set_result(function(*args))
            except Exception as exc:
                future.set_exception(exc)
            return future

    monkeypatch.setattr(bridge, "_connection", _FakeConnection())
    monkeypatch.setattr(bridge._sta, "get_sta_thread", lambda: _FakeStaThread())
    monkeypatch.setattr(
        bridge._sta,
        "shutdown",
        lambda: called.__setitem__("sta_shutdown", called["sta_shutdown"] + 1),
    )

    asyncio.run(bridge.shutdown())

    assert called["detach"] == 1
    assert called["disconnect"] == 0
    assert called["sta_shutdown"] == 1
    assert bridge._connection is None


def test_ensure_connected_rejects_unhealthy_fresh_start(monkeypatch):
    class _FakeStaThread:
        def submit(self, function, *args):
            future = concurrent.futures.Future()
            try:
                future.set_result(function(*args))
            except Exception as exc:
                future.set_exception(exc)
            return future

    class _FakeConnection:
        def __init__(self):
            self.state = ConnectionState.DISCONNECTED
            self.connect_calls = 0
            self.health_check_calls = 0

        def connect(self, visible):
            self.connect_calls += 1
            self.state = ConnectionState.CONNECTED
            return True

        def health_check(self):
            self.health_check_calls += 1
            return False

    connection = _FakeConnection()
    monkeypatch.setattr(bridge, "_connection", connection)
    monkeypatch.setattr(bridge._sta, "get_sta_thread", lambda: _FakeStaThread())

    with pytest.raises(BridgeConnectionError, match="did not remain available"):
        asyncio.run(bridge.ensure_connected())

    assert connection.connect_calls == 1
    assert connection.health_check_calls == 1


def test_start_returns_existing_connection_error_when_post_start_health_check_fails(monkeypatch):
    async def fail_start(*args, **kwargs):
        raise BridgeConnectionError("ConfigurationDesk did not remain available after startup.")

    monkeypatch.setattr(application_service, "ensure_connected", fail_start)

    payload = json.loads(asyncio.run(application_service.start()))

    assert payload["success"] is False
    assert payload["error_code"] == "COM_DISCONNECTED"


def test_get_status_uses_non_reconnecting_dispatch(monkeypatch):
    connection = SimpleNamespace()

    async def fake_dispatch(function, passed_connection, *args, **kwargs):
        assert function is application_service.application_com.get_status
        assert passed_connection is connection
        assert kwargs["reconnect"] is False
        assert kwargs["timeout_ms"] == observations.OBSERVATION_TIMEOUT_MS
        return {"connected": True, "project": "DemoProject"}

    monkeypatch.setattr(application_service, "get_connection", lambda: connection)
    monkeypatch.setattr(observations, "dispatch", fake_dispatch)

    payload = json.loads(asyncio.run(application_service.get_status()))

    assert payload["success"] is True
    assert payload["project"] == "DemoProject"


def test_diagnose_connection_uses_non_reconnecting_health_check(monkeypatch):
    connection = SimpleNamespace(state=SimpleNamespace(value="CONNECTED"))

    async def fake_dispatch(function, passed_connection, *args, **kwargs):
        assert function is application_service._inspect_connection
        assert passed_connection is connection
        assert kwargs["reconnect"] is False
        assert kwargs["timeout_ms"] == application_service._OBSERVATION_TIMEOUT_MS
        raise BridgeConnectionError("offline")

    monkeypatch.setattr(application_service, "get_connection", lambda: connection)
    monkeypatch.setattr(application_service, "dispatch", fake_dispatch)

    payload = json.loads(asyncio.run(application_service.diagnose_connection()))

    assert payload["success"] is True
    assert payload["diagnostics"]["health_check"] is False


def test_add_application_relies_on_add_activation_for_new_items():
    active_application = SimpleNamespace(Name="")

    class _FakeItem:
        def __init__(self, name: str):
            self.name = name
            self.activate_calls = []

        @property
        def Name(self):
            return self.name

        def Activate(self, auto_save_active_application):
            self.activate_calls.append(auto_save_active_application)
            active_application.Name = self.name

    class _FakeApplications:
        def __init__(self):
            self.items = {}

        def Contains(self, name: str):
            return name in self.items

        def Add(self, name: str, auto_save_active_application: bool):
            self.items[name] = _FakeItem(name)
            active_application.Name = name

        def Item(self, name: str):
            return self.items[name]

    applications = _FakeApplications()
    connection = SimpleNamespace(
        app=SimpleNamespace(
            ActiveProject=SimpleNamespace(Applications=applications),
            ActiveApplication=active_application,
        )
    )

    result = app_management_com.add_application(connection, "AppA")

    assert result["verified"] is True
    assert applications.Item("AppA").activate_calls == []


def test_activate_application_uses_documented_signature():
    active_application = SimpleNamespace(Name="OldApp")

    class _FakeItem:
        def __init__(self, name: str):
            self.name = name
            self.activate_calls = []

        @property
        def Name(self):
            return self.name

        def Activate(self, auto_save_active_application):
            self.activate_calls.append(auto_save_active_application)
            active_application.Name = self.name

    item = _FakeItem("AppB")

    class _FakeApplications:
        def Contains(self, name: str):
            return name == "AppB"

        def Item(self, name: str):
            assert name == "AppB"
            return item

    connection = SimpleNamespace(
        app=SimpleNamespace(
            ActiveProject=SimpleNamespace(Applications=_FakeApplications()),
            ActiveApplication=active_application,
        )
    )

    result = app_management_com.activate_application(connection, "AppB")

    assert result["verified"] is True
    assert item.activate_calls == [True]
