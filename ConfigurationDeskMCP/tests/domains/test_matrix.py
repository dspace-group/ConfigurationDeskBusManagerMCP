# -*- coding: utf-8 -*-
"""Domain: communication matrix tools (sources/tools/matrix.py).

Covers the matrix tools at the service layer (through the fake bridge) plus the
communication-matrix COM behavior and value-validation edge cases.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from configurationdesk_com_bridge.domains import matrix_com
from configurationdesk_com_bridge.errors import BridgeTimeoutError
from sources.services import matrix_service as matrix_svc

from tests.domains.conftest import run_ok

COVERS = (
    "add_communication_matrix",
    "remove_communication_matrix",
    "replace_communication_matrix_assignment",
    "list_matrices",
    "find_matrix_elements",
    "set_matrix_element_property",
)


# ── Service-layer tool coverage ────────────────────────────────────────────


def test_add_communication_matrix(fake_bridge):
    payload = run_ok(matrix_svc.add_communication_matrix("BusManagerBasicsDemo.arxml"))
    assert "CanBodyCluster" in payload["new_clusters"]


def test_remove_communication_matrix(fake_bridge):
    run_ok(matrix_svc.remove_communication_matrix(name="CanBodyCluster"))


def test_replace_communication_matrix_assignment(fake_bridge):
    payload = run_ok(
        matrix_svc.replace_communication_matrix_assignment(
            "Bus Configuration (1)", "BusManagerBasicsDemo"
        )
    )
    assert payload["verified"] is True
    assert payload["replaced_matrix_node"] == "BusManagerComMatrix"
    assert payload["new_matrix"] == "BusManagerBasicsDemo"
    assert payload["deprecated_nodes"] == []
    assert payload["warnings"] == []
    assert "check_conflicts" in payload["next_action"]


def test_replace_communication_matrix_assignment_reports_deprecated_nodes(monkeypatch):
    async def fake_dispatch(fn, *args, **kwargs):
        source = {"File name": "New.arxml", "File path": "mock-matrices", "Content hash": "new"}
        return {
            "bus_config_name": "BC1",
            "replaced_matrix_node": "Old",
            "new_matrix": "New",
            "assigned_matrices_before": ["Old"],
            "assigned_matrices_after": ["Old", "Old (deprecated 1)"],
            "expected_source": source,
            "assigned_sources_before": [{"File name": "Old.arxml"}],
            "assigned_sources_after": [source],
            "deprecated_nodes": ["Old (deprecated 1)"],
            "additional_replacing_conditions": {
                "requested": True,
                "previous": False,
                "restored": True,
            },
            "verified": True,
        }

    monkeypatch.setattr(matrix_svc, "dispatch", fake_dispatch)
    monkeypatch.setattr(matrix_svc, "get_connection", lambda: object())

    payload = run_ok(matrix_svc.replace_communication_matrix_assignment("BC1", "New", "Old", True))

    assert payload["deprecated_nodes"] == ["Old (deprecated 1)"]
    assert len(payload["warnings"]) == 1
    assert "Old (deprecated 1)" in payload["warnings"][0]


def test_replace_communication_matrix_assignment_maps_lookup_errors(monkeypatch):
    async def fake_dispatch(fn, *args, **kwargs):
        return {
            "error": True,
            "error_kind": "ambiguous_assigned_matrix",
            "detail": "Bus configuration 'BC1' has 2 assigned communication matrices",
            "assigned_matrices": ["A", "B"],
        }

    monkeypatch.setattr(matrix_svc, "dispatch", fake_dispatch)
    monkeypatch.setattr(matrix_svc, "get_connection", lambda: object())

    payload = json.loads(
        asyncio.run(matrix_svc.replace_communication_matrix_assignment("BC1", "New"))
    )

    assert payload["success"] is False
    assert payload["error_code"] == "AMBIGUOUS_MATRIX_ASSIGNMENT"
    assert "['A', 'B']" in payload["error"]
    assert "assigned_matrix_name" in payload["next_action"]


def test_list_matrices(fake_bridge):
    payload = run_ok(matrix_svc.list_matrices())
    assert payload["count"] == payload["total_count"] == 5
    assert payload["returned_count"] == 5


def test_list_matrices_paginates_each_view(fake_bridge):
    payload = run_ok(matrix_svc.list_matrices(offset=0, limit=2))

    assert payload["matrices"]["clusters"] == ["CanBodyCluster", "CanPowertrainCluster"]
    assert payload["matrices"]["ecus"] == ["CentralGatewayEcu"]
    assert payload["view_counts"] == {"clusters": 4, "ecus": 1}
    assert payload["returned_count"] == 3
    assert payload["next_offset"] == 2


def test_find_matrix_elements(fake_bridge):
    payload = run_ok(matrix_svc.find_matrix_elements(element_type="signal"))
    assert payload["count"] >= 1


def test_find_matrix_elements_paginates(fake_bridge):
    payload = run_ok(matrix_svc.find_matrix_elements(element_type="signal", offset=1, limit=1))

    assert payload["elements"] == []
    assert payload["count"] == payload["total_count"] == 1
    assert payload["returned_count"] == 0
    assert payload["next_offset"] is None


def test_set_matrix_element_property(fake_bridge):
    payload = run_ok(matrix_svc.set_matrix_element_property("Length", 1))
    assert payload["verified_count"] == 1


def test_set_matrix_element_property_rejects_bool_for_int(monkeypatch):
    async def fail_dispatch(*args, **kwargs):  # pragma: no cover - should not run
        raise AssertionError("dispatch should not be called for invalid value types")

    monkeypatch.setattr(matrix_svc, "dispatch", fail_dispatch)

    payload = json.loads(asyncio.run(matrix_svc.set_matrix_element_property("Length", True)))

    assert payload["success"] is False
    assert payload["error_code"] == "INVALID_VALUE_TYPE"
    assert "expects int" in payload["error"]


# ── COM-layer behavior (matrix_com) ────────────────────────────────────────


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


class _FakeNode:
    def __init__(self, name, mapping, roles=None):
        self.Name = name
        self.Roles = roles or []
        self.Properties = _FakePropertyCollection(mapping)


class _FakeRelation:
    def __init__(self, nodes):
        self._nodes = nodes
        self.xpaths: list[str] = []

    def FindByXPath(self, xpath, _context):
        self.xpaths.append(xpath)
        return list(self._nodes)


class _FakeRelations:
    def __init__(self, relation):
        self._relation = relation

    def Item(self, name):
        assert name in ("CommunicationMatricesByClusters", "CommunicationMatricesByEcus")
        return self._relation


class _FakeConnection:
    def __init__(self, relation):
        self.relations = _FakeRelations(relation)


def test_set_matrix_element_property_sets_length_by_alias():
    length_prop = _FakeProperty(initial_value=2)
    node = _FakeNode(
        "DoorLeftStatusCanIPdu",
        {"Length": length_prop},
        roles=["BusISignalIPdu"],
    )
    relation = _FakeRelation([node])
    connection = _FakeConnection(relation)

    result = matrix_com.set_matrix_element_property(
        connection,
        "Length",
        1,
        xpath="//*[@Name='DoorLeftStatusCanIPdu' and @Direction='TX']",
    )

    assert result["set_count"] == 1
    assert result["verified_count"] == 1
    assert result["property_name"] == "Length"
    assert length_prop.calls == [1]
    assert result["relation"] == "CommunicationMatricesByClusters"


def test_set_matrix_element_property_requires_allow_multiple_for_duplicates():
    first = _FakeNode("SpeedISignal", {"Initial value": _FakeProperty(initial_value=None)})
    second = _FakeNode("SpeedISignal", {"Initial value": _FakeProperty(initial_value=None)})
    relation = _FakeRelation([first, second])
    connection = _FakeConnection(relation)

    result = matrix_com.set_matrix_element_property(
        connection,
        "Initial value",
        1,
        element_name="SpeedISignal",
        view="ecus",
    )

    assert result["error"] is True
    assert "allow_multiple=true" in result["detail"]


# ── ReplaceCommunicationMatrixAssignment (matrix_com) ──────────────────────


class _Named:
    def __init__(self, name):
        self.Name = name
        self.Properties = _FakePropertyCollection(
            {
                "File name": _FakeProperty(f"{name}.arxml"),
                "File path": _FakeProperty("mock-matrices"),
                "Content hash": _FakeProperty(f"hash-{name}"),
            }
        )


class _FakeBusConfigRelation:
    def __init__(self, bus_configs, assigned):
        self._bus_configs = [_Named(name) for name in bus_configs]
        self.assigned = [_Named(name) for name in assigned]
        self.xpaths: list[str] = []

    def GetTopNodes(self):
        return list(self._bus_configs)

    def FindByXPath(self, xpath, _context):
        self.xpaths.append(xpath)
        return list(self.assigned)


class _FakeMatricesRelation:
    def __init__(self, names):
        self._nodes = [_Named(name) for name in names]

    def GetTopNodes(self):
        return list(self._nodes)


class _FakeReplaceRelations:
    def __init__(self, bus_rel, matrices_rel):
        self._items = {
            "BusConfigurations": bus_rel,
            "CommunicationMatricesByClusters": matrices_rel,
        }

    def Item(self, name):
        return self._items[name]


class _FakeBusManager:
    def __init__(self, bus_rel, conditions=False, deprecated=None, noop=False):
        self._bus_rel = bus_rel
        self.conditions = conditions
        self._deprecated = deprecated
        self._noop = noop
        self.calls: list[tuple[str, list]] = []

    def Configure(self, command, args):
        self.calls.append((command, list(args)))
        if command == "GetOrSetAdditionalReplacingConditions":
            if not args:
                return self.conditions
            self.conditions = args[0]
            return None
        if command == "ReplaceCommunicationMatrixAssignment" and not self._noop:
            old_matrix, new_matrix = args
            for node in self._bus_rel.assigned:
                if node.Name == old_matrix.Name:
                    node.Properties = new_matrix.Properties
            if self._deprecated:
                self._bus_rel.assigned.append(_Named(self._deprecated))
        return None


class _FakeReplaceConnection:
    def __init__(self, bus_configs, assigned, loaded, **bm_kwargs):
        self.bus_rel = _FakeBusConfigRelation(bus_configs, list(assigned))
        self.relations = _FakeReplaceRelations(self.bus_rel, _FakeMatricesRelation(loaded))
        self.busmanager = _FakeBusManager(self.bus_rel, **bm_kwargs)


def _replace_calls(connection):
    return [
        args
        for command, args in connection.busmanager.calls
        if command == "ReplaceCommunicationMatrixAssignment"
    ]


def test_replace_matrix_assignment_uses_documented_configure_call():
    connection = _FakeReplaceConnection(
        ["Bus Configuration (1)"],
        ["BusManagerComMatrix"],
        ["BusManagerComMatrix", "BusManagerBasicsDemo"],
    )

    result = matrix_svc._execute_matrix_replacement(
        connection, "Bus Configuration (1)", "BusManagerBasicsDemo"
    )

    assert matrix_svc._replacement_verified(result) is True
    assert result["replaced_matrix_node"] == "BusManagerComMatrix"
    assert result["deprecated_nodes"] == []
    (call,) = _replace_calls(connection)
    assert [node.Name for node in call] == ["BusManagerComMatrix", "BusManagerBasicsDemo"]
    assert connection.bus_rel.xpaths[0] == (
        '/BusConfiguration[@Name="Bus Configuration (1)"]//BusCommunicationMatrix'
    )
    assert all(
        command != "GetOrSetAdditionalReplacingConditions"
        for command, _ in connection.busmanager.calls
    )


def test_replace_matrix_assignment_reports_deprecated_node():
    connection = _FakeReplaceConnection(
        ["BC1"],
        ["Old"],
        ["Old", "New"],
        deprecated="Old (deprecated 1)",
    )

    result = matrix_svc._execute_matrix_replacement(connection, "BC1", "New", "Old")

    assert matrix_svc._replacement_verified(result) is True
    assert result["deprecated_nodes"] == ["Old (deprecated 1)"]
    assert result["assigned_matrices_after"] == ["Old", "Old (deprecated 1)"]


def test_replace_matrix_assignment_rejects_duplicate_loaded_names():
    connection = _FakeReplaceConnection(["BC1"], ["Old"], ["Old", "New", "New"])

    result = matrix_svc._execute_matrix_replacement(connection, "BC1", "New")

    assert result.get("error") is True
    assert result["error_kind"] == "ambiguous_loaded_matrix"
    assert connection.busmanager.calls == []


def test_replace_matrix_assignment_does_not_verify_a_noop():
    connection = _FakeReplaceConnection(["BC1"], ["Old"], ["New"], noop=True)

    result = matrix_svc._execute_matrix_replacement(connection, "BC1", "New")

    assert matrix_svc._replacement_verified(result) is False
    assert result["assigned_sources_after"] != [result["expected_source"]]


def test_replace_matrix_assignment_updates_every_matching_instance():
    connection = _FakeReplaceConnection(["BC1"], ["Old", "Old"], ["New"])

    result = matrix_svc._execute_matrix_replacement(connection, "BC1", "New")

    assert len(result["assigned_sources_after"]) == 2
    assert matrix_svc._replacement_verified(result) is True


def test_replace_matrix_assignment_rejects_different_sources_with_same_assigned_name():
    connection = _FakeReplaceConnection(["BC1"], ["Old", "Old"], ["New"])
    connection.bus_rel.assigned[1].Properties.Item("File path").Value = "mock-other-matrices"

    result = matrix_svc._execute_matrix_replacement(connection, "BC1", "New")

    assert result["error_kind"] == "ambiguous_assigned_source"
    assert connection.busmanager.calls == []


@pytest.mark.parametrize("property_name", ["File name", "File path", "Content hash"])
@pytest.mark.parametrize("node_index", [0, 1])
def test_replace_matrix_assignment_requires_readable_source_metadata(property_name, node_index):
    connection = _FakeReplaceConnection(["BC1"], ["Old"], ["New"])
    nodes = [
        connection.bus_rel.assigned[0],
        connection.relations.Item("CommunicationMatricesByClusters").GetTopNodes()[0],
    ]
    nodes[node_index].Properties.Item(property_name).Value = None

    result = matrix_svc._execute_matrix_replacement(connection, "BC1", "New")

    assert result["error_kind"] == "matrix_source_unavailable"
    assert connection.busmanager.calls == []


@pytest.mark.parametrize("property_name", ["File name", "File path", "Content hash"])
def test_replace_matrix_assignment_does_not_verify_mismatched_metadata(property_name):
    connection = _FakeReplaceConnection(["BC1"], ["Old"], ["New"])
    result = matrix_svc._execute_matrix_replacement(connection, "BC1", "New")
    result["assigned_sources_after"][0][property_name] = "different"

    assert matrix_svc._replacement_verified(result) is False


@pytest.mark.parametrize("remaining", [[], ["old"], ["new"], ["new", "old"]])
def test_replace_matrix_assignment_does_not_verify_partial_or_missing_updates(remaining):
    connection = _FakeReplaceConnection(["BC1"], ["Old", "Old"], ["New"])
    result = matrix_svc._execute_matrix_replacement(connection, "BC1", "New")
    result["assigned_sources_after"] = [
        result["expected_source"] if name == "new" else result["assigned_sources_before"][0]
        for name in remaining
    ]

    assert matrix_svc._replacement_verified(result) is False


@pytest.mark.parametrize(
    "noop, expected_code", [(True, "VERIFICATION_FAILED"), (False, "AMBIGUOUS_MATRIX_NAME")]
)
def test_replace_communication_matrix_assignment_reports_safety_failures(
    monkeypatch, noop, expected_code
):
    loaded = ["New"] if noop else ["New", "New"]
    connection = _FakeReplaceConnection(["BC1"], ["Old"], loaded, noop=noop)

    async def fake_dispatch(fn, *args, **kwargs):
        result = fn(*args, **kwargs)
        result["verified"] = True
        return result

    monkeypatch.setattr(matrix_svc, "dispatch", fake_dispatch)
    monkeypatch.setattr(matrix_svc, "get_connection", lambda: connection)

    payload = json.loads(
        asyncio.run(
            matrix_svc.replace_communication_matrix_assignment(
                "BC1", "New", use_additional_replacing_conditions=True
            )
        )
    )

    assert payload["success"] is False
    assert payload["error_code"] == expected_code
    assert connection.busmanager.conditions is False
    if not noop:
        assert connection.busmanager.calls == []


def test_replace_matrix_assignment_applies_and_restores_replacing_conditions():
    connection = _FakeReplaceConnection(["BC1"], ["Old"], ["New"], conditions=False)

    result = matrix_svc._execute_matrix_replacement(
        connection, "BC1", "New", use_additional_replacing_conditions=True
    )

    commands = [(command, args) for command, args in connection.busmanager.calls]
    replace_index = next(
        i for i, (cmd, _) in enumerate(commands) if cmd == "ReplaceCommunicationMatrixAssignment"
    )
    assert commands[replace_index - 2] == ("GetOrSetAdditionalReplacingConditions", [True])
    assert commands[replace_index - 1] == ("GetOrSetAdditionalReplacingConditions", [])
    assert commands[replace_index + 1] == ("GetOrSetAdditionalReplacingConditions", [False])
    assert commands[replace_index + 2] == ("GetOrSetAdditionalReplacingConditions", [])
    assert connection.busmanager.conditions is False
    assert result["additional_replacing_conditions"] == {
        "requested": True,
        "previous": False,
        "restored": True,
    }


@pytest.mark.parametrize("requested", [True, False])
def test_replace_rejects_an_ignored_requested_override(monkeypatch, requested):
    class IgnoredOverride(_FakeBusManager):
        def Configure(self, command, arguments):
            if command == "GetOrSetAdditionalReplacingConditions" and arguments == [requested]:
                self.calls.append((command, list(arguments)))
                return None
            return super().Configure(command, arguments)

    connection = _FakeReplaceConnection(["BC1"], ["Old"], ["New"])
    connection.busmanager = IgnoredOverride(connection.bus_rel, conditions=not requested)

    async def fake_dispatch(function, *arguments, **kwargs):
        return function(*arguments, **kwargs)

    monkeypatch.setattr(matrix_svc, "dispatch", fake_dispatch)
    monkeypatch.setattr(matrix_svc, "get_connection", lambda: connection)

    payload = json.loads(
        asyncio.run(
            matrix_svc.replace_communication_matrix_assignment("BC1", "New", "Old", requested)
        )
    )

    assert payload["success"] is False
    assert payload["error_code"] == "REPLACING_CONDITIONS_SET_FAILED"
    assert payload["additional_replacing_conditions"]["restored"] is True
    assert payload["retryable"] is False
    assert _replace_calls(connection) == []
    assert connection.busmanager.conditions is (not requested)


@pytest.mark.parametrize("requested", [True, False])
@pytest.mark.parametrize("readback", ["unreadable", "exception"])
def test_replace_aborts_if_requested_override_readback_fails(monkeypatch, requested, readback):
    class FailedReadback(_FakeBusManager):
        def __init__(self, relation):
            super().__init__(relation, conditions=not requested)
            self.reads = 0

        def Configure(self, command, arguments):
            if command == "GetOrSetAdditionalReplacingConditions" and not arguments:
                self.reads += 1
                if self.reads == 2:
                    if readback == "exception":
                        raise RuntimeError("override read failed")
                    return None
            return super().Configure(command, arguments)

    connection = _FakeReplaceConnection(["BC1"], ["Old"], ["New"])
    connection.busmanager = FailedReadback(connection.bus_rel)

    async def fake_dispatch(function, *arguments, **kwargs):
        return function(*arguments, **kwargs)

    monkeypatch.setattr(matrix_svc, "dispatch", fake_dispatch)
    monkeypatch.setattr(matrix_svc, "get_connection", lambda: connection)

    payload = json.loads(
        asyncio.run(
            matrix_svc.replace_communication_matrix_assignment("BC1", "New", "Old", requested)
        )
    )

    assert payload["success"] is False
    assert payload["error_code"] == "REPLACING_CONDITIONS_SET_FAILED"
    assert payload["additional_replacing_conditions"]["restored"] is True
    assert _replace_calls(connection) == []
    assert connection.busmanager.conditions is (not requested)


@pytest.mark.parametrize("requested", [True, False])
def test_override_failure_preserves_restoration_failure_priority(monkeypatch, requested):
    class FailedOverrideAndRestore(_FakeBusManager):
        def Configure(self, command, arguments):
            if command == "GetOrSetAdditionalReplacingConditions" and arguments:
                if arguments == [requested]:
                    return None
                raise RuntimeError("restoration refused")
            return super().Configure(command, arguments)

    connection = _FakeReplaceConnection(["BC1"], ["Old"], ["New"])
    connection.busmanager = FailedOverrideAndRestore(connection.bus_rel, conditions=not requested)

    async def fake_dispatch(function, *arguments, **kwargs):
        return function(*arguments, **kwargs)

    monkeypatch.setattr(matrix_svc, "dispatch", fake_dispatch)
    monkeypatch.setattr(matrix_svc, "get_connection", lambda: connection)

    payload = json.loads(
        asyncio.run(
            matrix_svc.replace_communication_matrix_assignment("BC1", "New", "Old", requested)
        )
    )

    assert payload["success"] is False
    assert payload["error_code"] == "REPLACING_CONDITIONS_RESTORE_FAILED"
    assert payload["additional_replacing_conditions"]["restored"] is False
    assert "restoration refused" in payload["error"]
    assert "requested replacing conditions" in payload["replacement_error"]
    assert _replace_calls(connection) == []


@pytest.mark.parametrize("original", [None, "unreadable", 7])
def test_replace_rejects_unreadable_original_setting(monkeypatch, original):
    connection = _FakeReplaceConnection(["BC1"], ["Old"], ["New"], conditions=original)

    async def fake_dispatch(function, *arguments, **kwargs):
        return function(*arguments, **kwargs)

    monkeypatch.setattr(matrix_svc, "dispatch", fake_dispatch)
    monkeypatch.setattr(matrix_svc, "get_connection", lambda: connection)

    payload = json.loads(
        asyncio.run(matrix_svc.replace_communication_matrix_assignment("BC1", "New", "Old", True))
    )

    assert payload["success"] is False
    assert payload["error_code"] == "REPLACING_CONDITIONS_UNAVAILABLE"
    assert connection.busmanager.calls == [("GetOrSetAdditionalReplacingConditions", [])]
    assert connection.busmanager.conditions == original


@pytest.mark.parametrize("failure", ["replacement", "verification", "success"])
def test_replace_reports_restoration_failure_on_error_paths(monkeypatch, failure):
    class FailingRestore(_FakeBusManager):
        def Configure(self, command, arguments):
            if command == "ReplaceCommunicationMatrixAssignment" and failure == "replacement":
                raise RuntimeError("replacement rejected")
            if command == "GetOrSetAdditionalReplacingConditions" and arguments == [False]:
                raise RuntimeError("restoration refused")
            return super().Configure(command, arguments)

    connection = _FakeReplaceConnection(["BC1"], ["Old"], ["New"])
    connection.busmanager = FailingRestore(connection.bus_rel, noop=failure == "verification")

    async def fake_dispatch(function, *arguments, **kwargs):
        return function(*arguments, **kwargs)

    monkeypatch.setattr(matrix_svc, "dispatch", fake_dispatch)
    monkeypatch.setattr(matrix_svc, "get_connection", lambda: connection)

    payload = json.loads(
        asyncio.run(matrix_svc.replace_communication_matrix_assignment("BC1", "New", "Old", True))
    )

    assert payload["success"] is False
    assert payload["error_code"] == "REPLACING_CONDITIONS_RESTORE_FAILED"
    assert payload["additional_replacing_conditions"]["restored"] is False
    assert "restoration refused" in payload["error"]
    assert "restor" in payload["next_action"].lower()
    assert connection.busmanager.conditions is True
    assert payload["replacement_verified"] is (failure == "success")
    assert payload["retryable"] is False


@pytest.mark.parametrize("failure", ["read", "set", "replace", "observe"])
def test_replace_preserves_option_status_on_other_failures(monkeypatch, failure):
    class FailingBusManager(_FakeBusManager):
        def Configure(self, command, arguments):
            if command == "GetOrSetAdditionalReplacingConditions" and not arguments:
                if failure == "read":
                    raise RuntimeError("option read failed")
            result = super().Configure(command, arguments)
            if (
                failure == "set"
                and command == "GetOrSetAdditionalReplacingConditions"
                and arguments == [True]
            ):
                raise RuntimeError("option set failed")
            if failure == "replace" and command == "ReplaceCommunicationMatrixAssignment":
                raise RuntimeError("replacement failed")
            return result

    connection = _FakeReplaceConnection(["BC1"], ["Old"], ["New"])
    connection.busmanager = FailingBusManager(connection.bus_rel)
    original_read = matrix_com.read_matrix_replacement_state
    reads = []

    def read_state(*arguments):
        reads.append(True)
        if failure == "observe" and len(reads) == 2:
            raise RuntimeError("observation failed")
        return original_read(*arguments)

    async def fake_dispatch(function, *arguments, **kwargs):
        return function(*arguments, **kwargs)

    monkeypatch.setattr(matrix_com, "read_matrix_replacement_state", read_state)
    monkeypatch.setattr(matrix_svc, "dispatch", fake_dispatch)
    monkeypatch.setattr(matrix_svc, "get_connection", lambda: connection)

    payload = json.loads(
        asyncio.run(matrix_svc.replace_communication_matrix_assignment("BC1", "New", "Old", True))
    )

    assert payload["success"] is False
    assert connection.busmanager.conditions is False
    assert payload["additional_replacing_conditions"]["restored"] is (
        None if failure == "read" else True
    )
    if failure in ("read", "set"):
        assert _replace_calls(connection) == []


def test_replace_checks_restoration_by_readback(monkeypatch):
    class IgnoredRestore(_FakeBusManager):
        def Configure(self, command, arguments):
            if command == "GetOrSetAdditionalReplacingConditions" and arguments == [False]:
                return None
            return super().Configure(command, arguments)

    connection = _FakeReplaceConnection(["BC1"], ["Old"], ["New"])
    connection.busmanager = IgnoredRestore(connection.bus_rel)

    async def fake_dispatch(function, *arguments, **kwargs):
        return function(*arguments, **kwargs)

    monkeypatch.setattr(matrix_svc, "dispatch", fake_dispatch)
    monkeypatch.setattr(matrix_svc, "get_connection", lambda: connection)

    payload = json.loads(
        asyncio.run(matrix_svc.replace_communication_matrix_assignment("BC1", "New", "Old", True))
    )

    assert payload["error_code"] == "REPLACING_CONDITIONS_RESTORE_FAILED"
    assert "Read-back" in payload["additional_replacing_conditions"]["restoration_error"]
    assert payload["replacement_verified"] is True


@pytest.mark.parametrize("option", [True, False])
def test_replace_does_not_rewrite_an_unchanged_option(option):
    connection = _FakeReplaceConnection(["BC1"], ["Old"], ["New"], conditions=option)

    result = matrix_svc._execute_matrix_replacement(connection, "BC1", "New", "Old", option)

    assert matrix_svc._replacement_verified(result) is True
    assert result["additional_replacing_conditions"]["restored"] is True
    assert not any(
        command == "GetOrSetAdditionalReplacingConditions" and arguments
        for command, arguments in connection.busmanager.calls
    )


@pytest.mark.parametrize("assigned", [["New"], ["Old", "New"]])
def test_replace_rejects_a_source_already_assigned(assigned):
    connection = _FakeReplaceConnection(["BC1"], assigned, ["Old", "New"])

    result = matrix_svc._execute_matrix_replacement(connection, "BC1", "New", assigned[0], True)

    assert result["error_kind"] == "new_matrix_already_assigned"
    assert connection.busmanager.calls == []


def test_replace_dispatch_failure_reports_unknown_restoration(monkeypatch):
    async def fake_dispatch(*arguments, **kwargs):
        raise BridgeTimeoutError("STA result unavailable")

    monkeypatch.setattr(matrix_svc, "dispatch", fake_dispatch)
    monkeypatch.setattr(matrix_svc, "get_connection", lambda: object())

    payload = json.loads(
        asyncio.run(matrix_svc.replace_communication_matrix_assignment("BC1", "New", "Old", True))
    )

    assert payload["success"] is False
    assert payload["error_code"] == "COM_TIMEOUT"
    assert payload["additional_replacing_conditions"] == {
        "requested": True,
        "previous": None,
        "restored": None,
    }


def test_replace_matrix_assignment_requires_name_when_ambiguous():
    connection = _FakeReplaceConnection(["BC1"], ["A", "B", "A"], ["New"])

    result = matrix_svc._execute_matrix_replacement(connection, "BC1", "New")

    assert result["error"] is True
    assert result["error_kind"] == "ambiguous_assigned_matrix"
    assert result["assigned_matrices"] == ["A", "B"]
    assert _replace_calls(connection) == []


def test_replace_matrix_assignment_validates_targets_before_configure():
    cases = [
        (("Missing", "New", None), "bus_config_not_found"),
        (("BC1", "New", "Other"), "assigned_matrix_not_found"),
        (("BC1", "Missing", None), "new_matrix_not_found"),
    ]
    for args, error_kind in cases:
        connection = _FakeReplaceConnection(["BC1"], ["Old"], ["Old", "New"])
        result = matrix_svc._execute_matrix_replacement(connection, *args)
        assert result["error"] is True, args
        assert result["error_kind"] == error_kind, args
        assert _replace_calls(connection) == [], args

    connection = _FakeReplaceConnection(["BC1"], [], ["New"])
    result = matrix_svc._execute_matrix_replacement(connection, "BC1", "New")
    assert result["error_kind"] == "no_assigned_matrix"


def test_replace_matrix_assignment_escapes_quotes_in_bus_config_name():
    connection = _FakeReplaceConnection(['My "BC"'], ["Old"], ["New"])

    matrix_svc._execute_matrix_replacement(connection, 'My "BC"', "New")

    assert connection.bus_rel.xpaths[0] == (
        "/BusConfiguration[@Name='My \"BC\"']//BusCommunicationMatrix"
    )
