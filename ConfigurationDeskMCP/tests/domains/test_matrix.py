# -*- coding: utf-8 -*-
"""Domain: communication matrix tools (sources/tools/matrix.py).

Covers the matrix tools at the service layer (through the fake bridge) plus the
communication-matrix COM behavior and value-validation edge cases.
"""

from __future__ import annotations

import asyncio
import json

from configurationdesk_com_bridge.domains import matrix_com
from sources.services import matrix_service as matrix_svc

from tests.domains.conftest import run_ok

COVERS = (
    "add_communication_matrix",
    "remove_communication_matrix",
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
