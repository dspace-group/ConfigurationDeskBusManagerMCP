# -*- coding: utf-8 -*-
"""Shared deterministic fake COM bridge for domain service tests.

The per-domain tool tests exercise the real service orchestration code with an
in-memory fake at the bridge boundary (``get_connection`` / ``dispatch`` /
``ensure_connected``). ``dispatch`` routes by the COM domain function's name to
a success-shaped return value, so only the COM call itself is simulated.

This keeps tests deterministic and reproducible without a real, installed
ConfigurationDesk.
"""

from __future__ import annotations

import importlib
import os
from types import SimpleNamespace
from typing import Any

# Every service module whose bridge boundary must be faked. Keep this in sync
# with the modules under ``sources.services`` that call ``dispatch``.
SERVICE_MODULES: tuple[str, ...] = (
    "sources.services.application_service",
    "sources.services.app_management_service",
    "sources.services.project_service",
    "sources.services.matrix_service",
    "sources.services.bus_config_service",
    "sources.services.model_topology_service",
    "sources.services.hardware_service",
    "sources.services.bus_access_service",
    "sources.services.io_functions_service",
    "sources.services.build_service",
    "sources.services.working_view_service",
    "sources.services.configuration_service",
    "sources.services._workflow_readiness",
    "sources.services._observations",
)

# COM operations that were intentionally removed; dispatching them is a bug.
REMOVED_OPERATIONS = frozenset(
    {
        "connect_function_ports_to_model_ports",
        "connect_io_function_blocks_to_model_ports",
    }
)


def _model_name(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]


def dispatch_returns() -> dict[str, Any]:
    """Map every COM domain function name → success-shaped return value.

    Values are either a static result or a callable receiving the domain
    function's real arguments (the leading connection argument excluded).
    """

    def _assign_ecu(
        bus_config_name=None, ecu_names=None, ecu_xpath=None, exclude_list="", part=None
    ):
        assert part in (None, "all", "simulated", "inspection", "manipulation")
        return {
            "status": "verified",
            "ecus": ecu_names or ["CentralGatewayEcu"],
            "parts": [part] if part else [],
        }

    def _assign_matrix(
        bus_config_name, element_name=None, element_type=None, matrix_xpath=None, part=None
    ):
        assert isinstance(bus_config_name, str) and bus_config_name
        assert part in (None, "all", "simulated", "inspection", "manipulation")
        assigned = [element_name] if element_name else ["CanBodyCluster"]
        return {"verified": True, "assigned": assigned, "parts": [part] if part else []}

    def _create_preconfigured_application_process(model_name, *args):
        assert isinstance(model_name, str) and model_name, (
            "create_preconfigured_application_process expects a non-empty model name"
        )
        return {"verified": True, "created_processes": ["AppProcess"], "model_name": model_name}

    return {
        # ── application_com / connection ──────────────────────────────────
        "disconnect": True,
        "get_status": {
            "connected": True,
            "project": "DemoProject",
            "project_name": "DemoProject",
            "application": "App",
            "application_name": "App",
        },
        "save_project": {"saved": True, "verified": True},
        "undo": {},
        "redo": {},
        # ── app_management_com ────────────────────────────────────────────
        "add_application": lambda name, *a: {"verified": True, "name": name},
        "activate_application": {"verified": True},
        "remove_application": {"verified": True},
        "list_applications": {"applications": ["App"], "active": "App"},
        # ── project_com ───────────────────────────────────────────────────
        "create_project": lambda *a: {"verified": True, "detail": "created"},
        "open_project": {"verified": True, "detail": "opened"},
        "close_project": {"verified": True},
        "remove_project": {"verified": True},
        "set_project_root": {"verified": True, "detail": "root set"},
        "list_projects": ["DemoProject"],
        "get_project_path": "D:/Projects/Demo",
        "backup_project": lambda path, *a: {"verified": True, "path": path},
        "open_project_from_backup": lambda backup_path, *a: {"verified": True, "path": backup_path},
        # ── matrix_com ────────────────────────────────────────────────────
        "add_communication_matrix": lambda path, *a: {
            "verified": True,
            "path": path,
            "new_clusters": [
                "CanBodyCluster",
                "CanPowertrainCluster",
                "LinDoorCluster",
                "LinSeatCluster",
            ],
            "new_ecus": ["CentralGatewayEcu"],
        },
        "remove_communication_matrix": {"verified": True, "removed": ["CanBodyCluster"]},
        "list_matrices": {
            "matrices": {
                "clusters": [
                    "CanBodyCluster",
                    "CanPowertrainCluster",
                    "LinDoorCluster",
                    "LinSeatCluster",
                ],
                "ecus": ["CentralGatewayEcu"],
            }
        },
        "find_matrix_elements": {
            "elements": [{"name": "EngineSpeed"}],
            "count": 1,
            "xpath_used": "//BusISignal",
        },
        "set_matrix_element_property": {
            "set_count": 1,
            "verified_count": 1,
            "mismatch_count": 0,
            "elements": ["matrix_element"],
            "property_name": "Length",
            "relation": "CommunicationMatricesByClusters",
        },
        # ── bus_config_com ────────────────────────────────────────────────
        "create": lambda name=None, *a: {"verified": True, "name": name or "BusConfiguration1"},
        "remove": {"verified": True, "removed": ["BusConfiguration1"]},
        "list_configs": ["RestbusBusConfig"],
        "find_elements": {"elements": [{"name": "FunctionPort1"}], "count": 1},
        "assign_ecu": _assign_ecu,
        "assign_matrix": _assign_matrix,
        "add_feature": {"verified": True, "elements": ["feature_element"]},
        "remove_elements": {"verified": True, "removed": ["feature_element"]},
        "generate_containers": {},
        "set_function_port_property": {"set_count": 1, "verified_count": 1, "mismatch_count": 0},
        "set_bus_config_element_property": {
            "set_count": 1,
            "verified_count": 1,
            "mismatch_count": 0,
            "elements": ["feature_element"],
            "property_name": "Countdown start value",
        },
        "assign_to_application_process": {"verified": True, "process": "AppProcess"},
        # ── model_topology_com ────────────────────────────────────────────
        "add_model": lambda path, *a: {
            "verified": True,
            "added": [_model_name(path)],
            "all_models": [_model_name(path)],
        },
        "replace_model": {"replaced_path": "demo.sic"},
        "remove_model": {"verified": True},
        "analyze_models": {},
        "create_application_process": {
            "verified": True,
            "process_name": "AppProcess",
            "default_task_set": True,
            "default_task_property": "ProvideDefaultTask",
            "default_task_name": "Periodic Task 1",
            "created_processes": ["AppProcess"],
        },
        "list_models": [
            "CentralGatewayECU_64-bit",
            "EngineAndBodyECUs_64-bit",
            "demosmd_io",
        ],
        "add_model_to_signal_chain": {"ports_added": 2},
        "add_model_port_to_signal_chain": {"port_added": "In1"},
        "list_model_ports": ["In1", "Out1"],
        "list_application_process_names": ["AppProcess"],
        # ── hardware_com ──────────────────────────────────────────────────
        "add_hardware_platform": {
            "platform_name": "SCALEXIO_1",
            "hardware_items": ["SCALEXIO_Rack"],
            "verified": True,
        },
        "add_hardware_element": lambda etype=None, *a: {
            "element_name": etype or "Element",
            "hardware_items": [etype or "Element"],
            "verified": True,
        },
        "add_processing_unit_application": {
            "processing_unit_created": True,
            "processing_unit_detail": "created",
        },
        "import_hardware_topology": {"verified": True, "hardware_items": ["SCALEXIO_Rack"]},
        "scan_hardware": {"verified": True, "hardware_items": ["SCALEXIO_Rack"]},
        "remove_hardware": {"verified": True},
        "refresh_platforms": {"platforms": ["SCALEXIO_1"]},
        "list_hardware_names": ["SCALEXIO_Rack"],
        "list_platforms": ["SCALEXIO_1"],
        # ── bus_access_com ────────────────────────────────────────────────
        "create_bus_function_block": {"verified": True, "properties": {}},
        "set_bus_function_block_property": {
            "verified": True,
            "value_set": "500000",
            "value_readback": "500000",
        },
        "list_bus_function_block_properties": {"properties": [], "count": 0},
        "list_bus_access_requests": {"requests": [f"req{i}" for i in range(8)], "count": 8},
        "assign_bus_access": {"verified": True, "assigned_configs": ["cfg"], "verified_count": 1},
        "list_assignable_channel_sets": {"channel_sets": ["ch0"], "count": 1},
        "assign_channel_set": {"channel_set": "ch0"},
        "auto_assign_channel_set": {},
        "assign_hardware_automatically": {
            "verified": True,
            "assigned_function_blocks": ["VoltageOut_FB", "VoltageIn_FB"],
        },
        "create_preconfigured_application_process": _create_preconfigured_application_process,
        "auto_connect_matching_io_function_blocks_to_model_ports": {
            "verified": True,
            "function_blocks": ["CAN_Restbus"],
            "links_before": 0,
            "links_after": 1,
            "new_links": 1,
        },
        # ── io_functions_com ──────────────────────────────────────────────
        "add_io_function_block": {"verified": True, "properties": {}},
        "list_io_function_block_types": {
            "types": ["Voltage Out", "Voltage In", "PWM Out", "Digital In"],
            "count": 4,
        },
        "connect_function_block_port_to_model_port": {"verified": True},
        # ── configuration_com ─────────────────────────────────────────────
        "list_configuration": [
            {"name": "App", "depth": 0, "roles": ["Application"]},
            {"name": "Periodic Task 1", "depth": 1, "roles": ["Task"]},
        ],
        # ── working_view_com ──────────────────────────────────────────────
        "check_conflicts": {"conflicts": [], "count": 0},
        "list_working_views": ["DefaultView"],
        "create_working_view": {"verified": True},
        "remove_working_view": {"removed": True, "verified": True},
        "clear_all_working_views": {"verified": True},
        "export_working_view": lambda name, path, *a: {"verified": True, "path": path},
        # ── build_com ─────────────────────────────────────────────────────
        "build_application": {
            "success": True,
            "result_folder": "D:/out",
            "rta_path": "D:/out/app.rta",
        },
        "get_build_result": "D:/out/app.rta",
    }


class FakeConnection(SimpleNamespace):
    """In-memory stand-in for the COM connection object."""

    is_connected = True
    state = SimpleNamespace(value="CONNECTED")

    def disconnect(self, save: bool = True) -> bool:  # pragma: no cover - faked via dispatch
        return True

    def health_check(self) -> bool:
        return True


def install(monkeypatch) -> FakeConnection:
    """Patch the bridge boundary in every service module with an in-memory fake."""
    returns = dispatch_returns()
    connection = FakeConnection()

    async def fake_dispatch(fn, *args, **kwargs):
        name = getattr(fn, "__name__", "")
        if name in REMOVED_OPERATIONS:
            raise AssertionError(f"Removed operation was dispatched: {name}")
        if name == "_inspect_connection":
            return {"connection_state": "CONNECTED", "health_check": True}
        if name not in returns:
            raise AssertionError(f"Unexpected dispatch target: {name}")
        handler = returns[name]
        if callable(handler):
            # Drop the leading connection argument before forwarding.
            return handler(*args[1:])
        return handler

    async def fake_ensure_connected(*args, **kwargs):
        return False

    for mod_name in SERVICE_MODULES:
        module = importlib.import_module(mod_name)
        monkeypatch.setattr(module, "dispatch", fake_dispatch, raising=False)
        monkeypatch.setattr(module, "get_connection", lambda: connection, raising=False)
        if hasattr(module, "ensure_connected"):
            monkeypatch.setattr(module, "ensure_connected", fake_ensure_connected, raising=False)

    return connection
