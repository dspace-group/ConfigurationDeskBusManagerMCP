# -*- coding: utf-8 -*-
"""Shared readiness guards for workflow-dependent services."""

from __future__ import annotations

from typing import Optional

from configurationdesk_com_bridge.domains import (
    bus_config_com,
    hardware_com,
    model_topology_com,
    verify_com,
)
from configurationdesk_com_bridge.errors import BridgePreconditionError

from sources.services._observations import dispatch_observation


async def require_model_ready(conn, model_name: Optional[str] = None) -> list[str]:
    models = await dispatch_observation(model_topology_com.list_models, conn)
    if not models:
        raise BridgePreconditionError(
            "No model is ready in the active application.",
            recovery_hint="Call `add_model` and wait for it to complete before running model-dependent tools.",
        )
    if model_name and model_name not in models:
        raise BridgePreconditionError(
            f"Model '{model_name}' is not ready in the active application.",
            recovery_hint="Call `add_model` for that model and wait until it is visible before running this tool.",
        )
    return models


async def require_model_ports_ready(conn, model_name: str) -> list[str]:
    await require_model_ready(conn, model_name)
    ports = await dispatch_observation(model_topology_com.list_model_ports, conn, model_name)
    if not ports:
        raise BridgePreconditionError(
            f"Model '{model_name}' has no observable model ports yet.",
            recovery_hint="If this is a Simulink model, call `analyze_models` and wait for completion before using port-dependent tools.",
        )
    return ports


async def require_application_process_ready(conn, process_name: Optional[str] = None) -> list[str]:
    processes = await dispatch_observation(verify_com.list_application_process_names, conn)
    if not processes:
        raise BridgePreconditionError(
            "No application process is ready in the active application.",
            recovery_hint="Call `create_application_process` or `create_preconfigured_application_process` and wait until it completes before running this tool.",
        )
    if process_name and process_name not in processes:
        raise BridgePreconditionError(
            f"Application process '{process_name}' is not ready in the active application.",
            recovery_hint="Create that application process first or omit `process_name` to use an existing one.",
        )
    return processes


async def require_bus_config_function_ports_ready(
    conn, bus_config_name: Optional[str] = None
) -> None:
    xpath = f'//*[@Name="{bus_config_name}"]//FunctionPort' if bus_config_name else "//FunctionPort"
    result = await dispatch_observation(bus_config_com.find_elements, conn, None, None, xpath)
    if result.get("count", 0) == 0:
        raise BridgePreconditionError(
            "No bus configuration function ports are ready yet.",
            recovery_hint=(
                "Add the required bus features first, then ensure the corresponding function ports are observable "
                "before connecting ports. In the common workflow this means calling `add_feature_to_bus_element`, "
                "then `find_bus_config_elements` to verify the actual ports. If the expected ports are missing, fix "
                "the feature assignment or XPath/port selection before retrying. Do NOT call `generate_bus_containers` "
                "just to make function ports appear."
            ),
        )


async def require_hardware_topology_ready(conn) -> list[str]:
    hardware_items = await dispatch_observation(hardware_com.list_hardware_names, conn)
    if not hardware_items:
        raise BridgePreconditionError(
            "No hardware topology with observable hardware items is ready in the active application.",
            recovery_hint=(
                "Call `add_hardware_platform` or `import_hardware_topology` and wait until hardware items are visible "
                "before assigning channel sets or building with download enabled."
            ),
        )
    return hardware_items
