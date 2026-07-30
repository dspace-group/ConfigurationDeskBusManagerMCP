# -*- coding: utf-8 -*-
"""Domain: application configuration tools (sources/tools/configuration.py)."""

from sources.services import configuration_service as config_svc

from tests.domains.conftest import run_ok

COVERS = ("list_configuration",)


def test_list_configuration(fake_bridge):
    payload = run_ok(config_svc.list_configuration())
    assert [entry["name"] for entry in payload["configuration"]] == ["App", "Periodic Task 1"]
    assert payload["count"] == payload["total_count"] == 2
    assert payload["returned_count"] == 2


def test_list_configuration_paginates(fake_bridge):
    payload = run_ok(config_svc.list_configuration(offset=1, limit=1))

    assert [entry["name"] for entry in payload["configuration"]] == ["Periodic Task 1"]
    assert payload["count"] == payload["total_count"] == 2
    assert payload["returned_count"] == 1
    assert payload["next_offset"] is None
