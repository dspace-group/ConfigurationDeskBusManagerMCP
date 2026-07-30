# -*- coding: utf-8 -*-
"""Domain: bus access and I/O function block tools (sources/tools/bus_access.py)."""

from sources.services import bus_access_service as access_svc

from tests.domains.conftest import run_ok

COVERS = (
    "create_io_function_block",
    "set_io_function_block_property",
    "list_io_function_block_properties",
    "list_bus_access_requests",
    "assign_bus_access",
    "list_assignable_channel_sets",
    "assign_channel_set",
    "auto_assign_channel_set",
    "assign_hardware_automatically",
    "auto_connect_matching_io_function_blocks_to_model_ports",
    "create_preconfigured_application_process",
)


def test_create_io_function_block(fake_bridge):
    payload = run_ok(access_svc.create_bus_function_block("CAN_Restbus", "CAN"))
    assert payload["name"] == "CAN_Restbus"


def test_set_io_function_block_property(fake_bridge):
    run_ok(access_svc.set_bus_function_block_property("CAN_Restbus", "BaudRate", "500000", "CAN"))


def test_list_io_function_block_properties(fake_bridge):
    run_ok(access_svc.list_bus_function_block_properties("CAN_Restbus", "CAN"))


def test_list_bus_access_requests(fake_bridge):
    payload = run_ok(access_svc.list_bus_access_requests())
    assert payload["count"] == 8
    assert payload["returned_count"] == 8
    assert payload["next_offset"] is None


def test_list_bus_access_requests_paginates(fake_bridge):
    payload = run_ok(access_svc.list_bus_access_requests(offset=2, limit=3))

    assert payload["requests"] == ["req2", "req3", "req4"]
    assert payload["count"] == payload["total_count"] == 8
    assert payload["returned_count"] == 3
    assert payload["next_offset"] == 5


def test_assign_bus_access(fake_bridge):
    run_ok(access_svc.assign_bus_access("CAN_Restbus"))


def test_list_assignable_channel_sets(fake_bridge):
    # Requires a hardware topology; the fake bridge satisfies the readiness guard.
    run_ok(access_svc.list_assignable_channel_sets("CAN_Restbus", "CAN"))


def test_assign_channel_set(fake_bridge):
    run_ok(access_svc.assign_channel_set("CAN_Restbus", 0, "CAN"))


def test_auto_assign_channel_set(fake_bridge):
    run_ok(access_svc.auto_assign_channel_set("CAN_Restbus", "CAN"))


def test_assign_hardware_automatically(fake_bridge):
    run_ok(access_svc.assign_hardware_automatically())


def test_auto_connect_matching_io_function_blocks_to_model_ports(fake_bridge):
    # Requires a ready model and application process; satisfied by the fake bridge.
    run_ok(access_svc.auto_connect_matching_io_function_blocks_to_model_ports())


def test_create_preconfigured_application_process(fake_bridge):
    run_ok(access_svc.create_preconfigured_application_process("demosmd_io"))
