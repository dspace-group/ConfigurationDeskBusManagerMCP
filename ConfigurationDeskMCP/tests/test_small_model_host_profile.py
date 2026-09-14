# -*- coding: utf-8 -*-
"""Keep the repository small-model host profile aligned with the MCP inventory."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytest.importorskip("mcp")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PROFILE = _REPO_ROOT / "docs" / "small-model-host-profile.md"
_TOOL_REFERENCE = re.compile(r"`([a-z][a-z0-9_]*)`")
_ENVELOPE_FIELDS = {"next_action", "recovery_hint"}
_REQUIRED_RULES = (
    "`start_configurationdesk`",
    "`success=false`",
    "`verified=false`",
    "`retryable=false`",
    "`next_action`",
    "`check_conflicts`",
)
_APPLICATION_ROUTING_RULE = (
    "`add_application` after creating or\n"
    "  opening the project. Use `create_application_process` only for execution\n"
    "  scheduling"
)
_ROUTING_RULES = (
    "`create_bus_configuration`",
    "`create_io_function_block`",
    "`add_io_function_block`",
    "`assign_ecu_to_bus_config`",
    "`assign_matrix_to_bus_config`",
    "`set_matrix_element_property`",
    "`set_bus_config_element_property`",
    "`set_function_port_property`",
    "`set_io_function_block_property`",
    "`add_hardware_platform`",
    "`import_hardware_topology`",
    "`add_processing_unit_application`",
    "`add_model_to_signal_chain`",
    "`add_model_port_to_signal_chain`",
    "`create_preconfigured_application_process`",
    "`create_application_process`",
    "`assign_channel_set`",
    "`auto_assign_channel_set`",
    "`assign_hardware_automatically`",
    "`auto_connect_matching_io_function_blocks_to_model_ports`",
    "`connect_function_block_port_to_model_port`",
    "`list_matrices`",
    "`find_matrix_elements`",
    "`list_bus_configurations`",
    "`find_bus_config_elements`",
    "`list_configuration`",
    "`analyze_models`",
    "`build_application`",
    "`get_build_result`",
    "`remove_project`",
    "`remove_application`",
    "`remove_model`",
    "`remove_bus_configuration`",
    "`remove_bus_config_elements`",
)


def test_small_model_host_profile_references_registered_tools_only():
    import sources.server.app  # noqa: F401
    from sources.server import registry

    profile = _PROFILE.read_text(encoding="utf-8")
    referenced_tools = set(_TOOL_REFERENCE.findall(profile)) - _ENVELOPE_FIELDS

    assert referenced_tools <= set(registry.registered_tool_names())


def test_small_model_host_profile_keeps_mandatory_safety_rules():
    profile = _PROFILE.read_text(encoding="utf-8")

    for rule in _REQUIRED_RULES:
        assert rule in profile


def test_small_model_host_profile_distinguishes_application_from_process():
    profile = _PROFILE.read_text(encoding="utf-8")

    assert _APPLICATION_ROUTING_RULE in profile


def test_small_model_host_profile_covers_high_risk_tool_routing():
    profile = _PROFILE.read_text(encoding="utf-8")

    for rule in _ROUTING_RULES:
        assert rule in profile
