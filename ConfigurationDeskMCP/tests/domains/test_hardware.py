# -*- coding: utf-8 -*-
"""Domain: hardware management tools (sources/tools/hardware.py)."""

from sources.services import hardware_service as hw_svc

from tests.domains.conftest import run_ok

COVERS = (
    "add_hardware_platform",
    "add_hardware_element",
    "import_hardware_topology",
    "scan_hardware",
    "remove_hardware",
    "list_platforms",
    "refresh_platforms",
)


def test_add_hardware_platform(fake_bridge):
    payload = run_ok(hw_svc.add_hardware_platform([], "SCALEXIO"))
    assert payload["platform_name"] == "SCALEXIO_1"


def test_add_hardware_element(fake_bridge):
    payload = run_ok(hw_svc.add_hardware_element("DS1513"))
    assert payload["element_name"] == "DS1513"


def test_import_hardware_topology(fake_bridge):
    run_ok(hw_svc.import_hardware_topology("D:/topology.htfx"))


def test_scan_hardware(fake_bridge):
    run_ok(hw_svc.scan_hardware("SCALEXIO_1"))


def test_remove_hardware(fake_bridge):
    run_ok(hw_svc.remove_hardware("SCALEXIO_Rack"))


def test_list_platforms(fake_bridge):
    run_ok(hw_svc.list_platforms())


def test_refresh_platforms(fake_bridge):
    run_ok(hw_svc.refresh_platforms())
