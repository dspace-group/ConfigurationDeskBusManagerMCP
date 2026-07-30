# -*- coding: utf-8 -*-
"""Tests for the _verify helpers and the response functions."""

import json
import os
import tempfile
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from configurationdesk_com_bridge.domains import model_topology_com
from configurationdesk_com_bridge.domains import verify_com
from configurationdesk_com_bridge.domains.verify_com import (
    build_xpath,
    count_config_nodes,
    count_top_nodes,
    get_top_node_names,
    list_model_names,
    verify_active_application,
    verify_active_project,
    verify_contains,
    verify_count_changed,
    verify_exists,
    verify_file_exists,
    verify_no_active_project,
    verify_not_contains,
    verify_not_exists,
    wait_for_new_names,
    wait_for_state,
    xpath_result_count,
)
from sources.tools._responses import error_response, success_response, unverified_response


# ── build_xpath ────────────────────────────────────────────────────────────


class TestBuildXPath:
    def test_type_only(self):
        assert build_xpath("BusISignalValue") == "//BusISignalValue"

    def test_name_only(self):
        assert build_xpath(name="LinDoorCluster") == '//*[@Name="LinDoorCluster"]'

    def test_type_and_name(self):
        result = build_xpath("BusEcu", "ECU1")
        assert result == '//*[@Name="ECU1"][self::BusEcu]'

    def test_no_params_raises(self):
        with pytest.raises(ValueError, match="At least one"):
            build_xpath()


# ── Response helpers ───────────────────────────────────────────────────────


class TestResponses:
    def test_success_response_json(self):
        data = json.loads(success_response(message="ok", verified=True))
        assert data["success"] is True
        assert data["verified"] is True
        assert data["message"] == "ok"

    def test_unverified_response_json(self):
        data = json.loads(unverified_response(message="maybe"))
        assert data["success"] is True
        assert data["verified"] is False
        assert data["message"] == "maybe"

    def test_error_response_json(self):
        data = json.loads(error_response("boom"))
        assert data["success"] is False
        assert data["error"] == "boom"
        assert data["retryable"] is False

    def test_error_response_transient(self):
        data = json.loads(error_response("retry", transient=True))
        assert data["retryable"] is True


# ── Relation helpers (mocked COM) ──────────────────────────────────────────


def _make_connection_with_nodes(relation_name, node_names):
    """Create a mock connection whose relation returns nodes with given names."""
    conn = MagicMock()
    nodes = []
    for n in node_names:
        node = MagicMock()
        node.Name = n
        nodes.append(node)
    rel = MagicMock()
    rel.GetTopNodes.return_value = iter(nodes)

    def item_side_effect(name):
        if name == relation_name:
            return rel
        raise KeyError(name)

    conn.relations.Item.side_effect = item_side_effect
    return conn, rel


class TestGetTopNodeNames:
    def test_returns_names(self):
        conn, _ = _make_connection_with_nodes("BusConfigurations", ["A", "B", "C"])
        assert get_top_node_names("BusConfigurations", conn) == ["A", "B", "C"]

    def test_empty(self):
        conn, _ = _make_connection_with_nodes("BusConfigurations", [])
        assert get_top_node_names("BusConfigurations", conn) == []


class TestCountTopNodes:
    def test_correct_count(self):
        conn, _ = _make_connection_with_nodes("BusConfigurations", ["A", "B"])
        assert count_top_nodes("BusConfigurations", conn) == 2


class TestXPathResultCount:
    def test_returns_count(self):
        conn, rel = _make_connection_with_nodes("BusConfigurations", [])
        items = [MagicMock(), MagicMock()]
        rel.FindByXPath.return_value = iter(items)
        assert xpath_result_count("BusConfigurations", "//BusEcu", conn) == 2


# ── Verification primitives ───────────────────────────────────────────────


class TestVerifyExists:
    def test_found(self):
        conn, _ = _make_connection_with_nodes("Rel", ["Alpha", "Beta"])
        ok, msg = verify_exists("Rel", "Alpha", conn)
        assert ok is True
        assert "found" in msg.lower()

    def test_not_found(self):
        conn, _ = _make_connection_with_nodes("Rel", ["Alpha", "Beta"])
        ok, msg = verify_exists("Rel", "Gamma", conn)
        assert ok is False
        assert "NOT found" in msg


class TestVerifyNotExists:
    def test_absent(self):
        conn, _ = _make_connection_with_nodes("Rel", ["Alpha"])
        ok, msg = verify_not_exists("Rel", "Beta", conn)
        assert ok is True

    def test_still_present(self):
        conn, _ = _make_connection_with_nodes("Rel", ["Alpha"])
        ok, msg = verify_not_exists("Rel", "Alpha", conn)
        assert ok is False


class TestVerifyCountChanged:
    def test_increased(self):
        conn, _ = _make_connection_with_nodes("Rel", ["A", "B", "C"])
        ok, msg = verify_count_changed("Rel", conn, old_count=2, direction="increased")
        assert ok is True

    def test_not_increased(self):
        conn, _ = _make_connection_with_nodes("Rel", ["A", "B"])
        ok, msg = verify_count_changed("Rel", conn, old_count=2, direction="increased")
        assert ok is False

    def test_decreased(self):
        conn, _ = _make_connection_with_nodes("Rel", ["A"])
        ok, msg = verify_count_changed("Rel", conn, old_count=3, direction="decreased")
        assert ok is True


class TestVerifyContains:
    def test_contains_true(self):
        coll = MagicMock()
        coll.Contains.return_value = True
        ok, msg = verify_contains(coll, "X")
        assert ok is True

    def test_contains_false(self):
        coll = MagicMock()
        coll.Contains.return_value = False
        ok, msg = verify_contains(coll, "X")
        assert ok is False


class TestVerifyNotContains:
    def test_absent(self):
        coll = MagicMock()
        coll.Contains.return_value = False
        ok, msg = verify_not_contains(coll, "X")
        assert ok is True

    def test_present(self):
        coll = MagicMock()
        coll.Contains.return_value = True
        ok, msg = verify_not_contains(coll, "X")
        assert ok is False


class TestVerifyActiveProject:
    def test_matches(self):
        conn = MagicMock()
        conn.app.ActiveProject.Name = "MyProject"
        ok, msg = verify_active_project(conn, "MyProject")
        assert ok is True

    def test_mismatch(self):
        conn = MagicMock()
        conn.app.ActiveProject.Name = "Other"
        ok, msg = verify_active_project(conn, "MyProject")
        assert ok is False


class TestVerifyActiveApplication:
    def test_matches(self):
        conn = MagicMock()
        # Modern COM path: ActiveApplication.Name
        conn.app.ActiveApplication.Name = "App1"
        # Legacy COM path: ActiveApplication.Application.Name
        conn.app.ActiveApplication.Application.Name = "App1"
        ok, msg = verify_active_application(conn, "App1")
        assert ok is True

    def test_mismatch(self):
        conn = MagicMock()
        conn.app.ActiveApplication.Name = "Other"
        conn.app.ActiveApplication.Application.Name = "Other"
        ok, msg = verify_active_application(conn, "App1")
        assert ok is False


class TestVerifyNoActiveProject:
    def test_no_project(self):
        conn = MagicMock()
        conn.app.ActiveProject = None
        ok, msg = verify_no_active_project(conn)
        assert ok is True

    def test_project_still_active(self):
        conn = MagicMock()
        conn.app.ActiveProject.Name = "StillHere"
        ok, msg = verify_no_active_project(conn)
        assert ok is False


class TestVerifyFileExists:
    def test_exists(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"test")
            path = f.name
        try:
            ok, msg = verify_file_exists(path)
            assert ok is True
        finally:
            os.unlink(path)

    def test_not_exists(self):
        ok, msg = verify_file_exists("/nonexistent/path/file.xyz")
        assert ok is False


# ── Model topology helpers ─────────────────────────────────────────────────


class TestListModelNames:
    def test_from_application_config(self):
        conn = MagicMock()
        rel = MagicMock()
        conn.relations.Item.return_value = rel

        top_node = MagicMock()
        top_node.Name = "App"
        elem = MagicMock()
        elem.Name = "MyModel"
        elem.Roles = ["ModelRole"]

        rel.GetTopNodes.return_value = [top_node]
        rel.GetElements.return_value = [elem]

        names = list_model_names(conn)
        assert "MyModel" in names

    def test_from_model_topology_filters_non_string_names(self):
        conn = MagicMock()

        bogus = MagicMock()
        bogus.Name = MagicMock()

        model = MagicMock()
        model.Name = "RealModel"

        conn.model_topology = [bogus, model]

        names = list_model_names(conn)

        assert names == ["RealModel"]


class TestModelTopologyVerification:
    def test_add_model_reports_added_names(self, monkeypatch):
        configured = []

        class _FakeTopology:
            def Configure(self, action, args):
                configured.append((action, args))

        connection = SimpleNamespace(model_topology=_FakeTopology())
        observed_names = iter(
            [
                ["ExistingModel"],
                ["ExistingModel", "AddedModel"],
            ]
        )

        monkeypatch.setattr(
            model_topology_com,
            "list_model_names",
            lambda _connection: next(observed_names),
        )
        monkeypatch.setattr(
            model_topology_com,
            "wait_for_new_names",
            lambda read_names, before_names, timeout_s: (
                True,
                ["AddedModel"],
                read_names(),
            ),
        )

        result = model_topology_com.add_model(connection, "demo.sic", analyze=True)

        assert result["verified"] is True
        assert result["added"] == ["AddedModel"]
        assert result["all_models"] == ["AddedModel", "ExistingModel"]
        assert configured == [("AddModel", [os.path.abspath("demo.sic"), False, "", True])]

    def test_remove_model_uses_remaining_names_for_verification(self, monkeypatch):
        configured = []

        class _FakeTopology:
            def Configure(self, action, args):
                configured.append((action, args))

        connection = SimpleNamespace(model_topology=_FakeTopology())

        monkeypatch.setattr(
            model_topology_com,
            "list_model_names",
            lambda _connection: ["OtherModel"],
        )

        result = model_topology_com.remove_model(connection, "RemovedModel")

        assert result["verified"] is True
        assert result["remaining"] == ["OtherModel"]
        assert configured == [("RemoveModel", ["RemovedModel"])]


class TestCountConfigNodes:
    def test_counts_top_and_children(self):
        conn = MagicMock()
        rel = MagicMock()
        conn.relations.Item.return_value = rel

        top1 = MagicMock()
        child1 = MagicMock()
        child2 = MagicMock()

        rel.GetTopNodes.return_value = [top1]
        rel.GetElements.return_value = [child1, child2]

        # 1 top + 2 children = 3
        assert count_config_nodes(conn) == 3


class TestWaitForState:
    def test_returns_when_state_becomes_ready(self, monkeypatch):
        states = iter([0, 0, 1])
        monkeypatch.setattr(verify_com, "_pump_waiting_messages", lambda: None)
        monkeypatch.setattr(verify_com.time, "sleep", lambda _seconds: None)

        ok, state = wait_for_state(
            lambda: next(states),
            lambda value: value == 1,
            timeout_s=0.5,
            poll_interval_s=0.0,
        )

        assert ok is True
        assert state == 1

    def test_returns_last_state_on_timeout(self, monkeypatch):
        monkeypatch.setattr(verify_com, "_pump_waiting_messages", lambda: None)
        monkeypatch.setattr(verify_com.time, "sleep", lambda _seconds: None)

        ok, state = wait_for_state(
            lambda: 0,
            lambda value: value == 1,
            timeout_s=0.0,
            poll_interval_s=0.0,
        )

        assert ok is False
        assert state == 0


class TestWaitForNewNames:
    def test_detects_eventual_new_name(self, monkeypatch):
        snapshots = iter(
            [
                ["Existing"],
                ["Existing"],
                ["Existing", "AddedLater"],
            ]
        )
        monkeypatch.setattr(verify_com, "_pump_waiting_messages", lambda: None)
        monkeypatch.setattr(verify_com.time, "sleep", lambda _seconds: None)

        ok, added, current = wait_for_new_names(
            lambda: next(snapshots),
            ["Existing"],
            timeout_s=0.5,
            poll_interval_s=0.0,
        )

        assert ok is True
        assert added == ["AddedLater"]
        assert current == ["Existing", "AddedLater"]
