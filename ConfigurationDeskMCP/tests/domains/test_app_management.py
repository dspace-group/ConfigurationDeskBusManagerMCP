# -*- coding: utf-8 -*-
"""Domain: application management tools (sources/tools/app_management.py)."""

from sources.services import app_management_service as appmgmt_svc

from tests.domains.conftest import run_ok

COVERS = (
    "add_application",
    "activate_application",
    "remove_application",
    "list_applications",
    "add_processing_unit_application",
)


def test_add_application(fake_bridge):
    payload = run_ok(appmgmt_svc.add_application("RestbusApp"))
    assert payload["name"] == "RestbusApp"


def test_activate_application(fake_bridge):
    run_ok(appmgmt_svc.activate_application("RestbusApp"))


def test_remove_application(fake_bridge):
    run_ok(appmgmt_svc.remove_application("RestbusApp"))


def test_list_applications(fake_bridge):
    run_ok(appmgmt_svc.list_applications())


def test_add_processing_unit_application(fake_bridge):
    run_ok(appmgmt_svc.add_processing_unit_application())
