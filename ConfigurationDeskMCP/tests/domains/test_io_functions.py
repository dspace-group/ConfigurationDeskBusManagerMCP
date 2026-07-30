# -*- coding: utf-8 -*-
"""Domain: I/O functions library tools (sources/tools/io_functions.py)."""

from sources.services import io_functions_service as io_svc

from tests.domains.conftest import run_ok

COVERS = (
    "add_io_function_block",
    "list_io_function_block_types",
    "connect_function_block_port_to_model_port",
)


def test_list_io_function_block_types(fake_bridge):
    payload = run_ok(io_svc.list_io_function_block_types())
    assert "Voltage Out" in payload["types"]


def test_add_io_function_block(fake_bridge):
    payload = run_ok(io_svc.add_io_function_block("Voltage Out", "VoltageOut_FB"))
    assert payload["name"] == "VoltageOut_FB"


def test_connect_function_block_port_to_model_port(fake_bridge):
    run_ok(
        io_svc.connect_function_block_port_to_model_port(
            "VoltageOut_FB", "Out1", "demosmd_io", "In1"
        )
    )
