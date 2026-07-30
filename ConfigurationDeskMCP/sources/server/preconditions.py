# -*- coding: utf-8 -*-
"""Precondition guards for MCP tools.

Provides a decorator that validates workflow prerequisites before tool execution.
When a precondition fails, returns a structured error guiding the model to the
correct next action instead of a cryptic COM error.
"""

from __future__ import annotations

import functools
import json
from typing import Any, Callable, Coroutine

from configurationdesk_com_bridge.errors import BridgeError
from sources.models.envelope_builder import tool_error_result
from sources.tools._responses import error_response
from sources.utils.logger import get_logger

logger = get_logger(__name__)


# ── Precondition check functions ──────────────────────────────────────────────


def _check_connection() -> tuple[bool, str]:
    """Check if COM bridge is connected."""
    try:
        from configurationdesk_com_bridge import get_connection  # noqa: PLC0415

        conn = get_connection()
        if conn.is_connected:
            return True, ""
        return False, "ConfigurationDesk is not connected."
    except RuntimeError:
        return False, "COM bridge not initialized."


async def _check_project() -> tuple[bool, str]:
    """Check if a project is open."""
    from configurationdesk_com_bridge import dispatch, get_connection  # noqa: PLC0415
    from configurationdesk_com_bridge.domains import application_com  # noqa: PLC0415

    try:
        conn = get_connection()
    except RuntimeError:
        return False, "COM bridge not initialized."
    if not conn.is_connected:
        return False, "ConfigurationDesk is not connected."
    status = await dispatch(application_com.get_status, conn)
    if status.get("project_name") or status.get("project"):
        return True, ""
    return False, "No project is open."


async def _check_application() -> tuple[bool, str]:
    """Check if an application exists."""
    from configurationdesk_com_bridge import dispatch, get_connection  # noqa: PLC0415
    from configurationdesk_com_bridge.domains import application_com  # noqa: PLC0415

    try:
        conn = get_connection()
    except RuntimeError:
        return False, "COM bridge not initialized."
    if not conn.is_connected:
        return False, "ConfigurationDesk is not connected."
    status = await dispatch(application_com.get_status, conn)
    if status.get("application_name") or status.get("application"):
        return True, ""
    return False, "No application exists in the project."


async def _check_bus_config() -> tuple[bool, str]:
    """Check if at least one bus configuration exists."""
    from configurationdesk_com_bridge import dispatch, get_connection  # noqa: PLC0415
    from configurationdesk_com_bridge.domains import bus_config_com  # noqa: PLC0415

    try:
        conn = get_connection()
    except RuntimeError:
        return False, "COM bridge not initialized."
    if not conn.is_connected:
        return False, "ConfigurationDesk is not connected."
    configs = await dispatch(bus_config_com.list_configs, conn)
    if configs:
        return True, ""
    return False, "No bus configuration exists."


async def _check_model() -> tuple[bool, str]:
    """Check if at least one model is ready."""
    from configurationdesk_com_bridge import dispatch, get_connection  # noqa: PLC0415
    from configurationdesk_com_bridge.domains import model_topology_com  # noqa: PLC0415

    try:
        conn = get_connection()
    except RuntimeError:
        return False, "COM bridge not initialized."
    if not conn.is_connected:
        return False, "ConfigurationDesk is not connected."
    models = await dispatch(model_topology_com.list_models, conn)
    if models:
        return True, ""
    return False, "No model is ready in the active application."


async def _check_application_process() -> tuple[bool, str]:
    """Check if at least one application process is ready."""
    from configurationdesk_com_bridge import dispatch, get_connection  # noqa: PLC0415
    from configurationdesk_com_bridge.domains import verify_com  # noqa: PLC0415

    try:
        conn = get_connection()
    except RuntimeError:
        return False, "COM bridge not initialized."
    if not conn.is_connected:
        return False, "ConfigurationDesk is not connected."
    processes = await dispatch(verify_com.list_application_process_names, conn)
    if processes:
        return True, ""
    return False, "No application process is ready in the active application."


async def _check_hardware_topology() -> tuple[bool, str]:
    """Check if a hardware topology with observable items exists."""
    from configurationdesk_com_bridge import dispatch, get_connection  # noqa: PLC0415
    from configurationdesk_com_bridge.domains import hardware_com  # noqa: PLC0415

    try:
        conn = get_connection()
    except RuntimeError:
        return False, "COM bridge not initialized."
    if not conn.is_connected:
        return False, "ConfigurationDesk is not connected."
    hardware_items = await dispatch(hardware_com.list_hardware_names, conn)
    if hardware_items:
        return True, ""
    return False, "No hardware topology with observable hardware items exists."


# ── Precondition registry ─────────────────────────────────────────────────────

# Maps precondition name → (check_fn, recovery_hint, next_action_tool)
_PRECONDITIONS: dict[str, tuple[Any, str, str]] = {
    "connection": (
        _check_connection,
        "ConfigurationDesk must be running and connected.",
        "start_configurationdesk",
    ),
    "project": (
        _check_project,
        "A project must be open before this operation.",
        "create_project",
    ),
    "application": (
        _check_application,
        "An application must exist before this operation.",
        "add_application",
    ),
    "bus_config": (
        _check_bus_config,
        "A bus configuration must exist before creating I/O function blocks. "
        "Call `create_bus_configuration` first.",
        "create_bus_configuration",
    ),
    "model": (
        _check_model,
        "A model must be added and ready before this operation.",
        "add_model",
    ),
    "application_process": (
        _check_application_process,
        "An application process must exist before this operation.",
        "create_application_process",
    ),
    "hardware_topology": (
        _check_hardware_topology,
        "A hardware topology with observable hardware items must exist before this operation.",
        "add_hardware_platform",
    ),
}


# ── Decorator ─────────────────────────────────────────────────────────────────


def with_preconditions(
    *precondition_names: str,
) -> Callable[
    [Callable[..., Coroutine[Any, Any, str]]],
    Callable[..., Coroutine[Any, Any, str]],
]:
    """Decorator that validates preconditions before executing a tool handler.

    Usage::

        @with_preconditions("connection", "project", "bus_config")
        async def create_io_function_block(input: ...) -> str:
            ...

    If a precondition fails, returns a structured JSON error response with
    ``next_action`` pointing to the tool the model should call instead.
    """

    def decorator(
        func: Callable[..., Coroutine[Any, Any, str]],
    ) -> Callable[..., Coroutine[Any, Any, str]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> str:
            for name in precondition_names:
                if name not in _PRECONDITIONS:
                    logger.warning("Unknown precondition: %s", name)
                    continue

                check_fn, hint, next_tool = _PRECONDITIONS[name]

                # Some checks are sync, some async
                if callable(check_fn):
                    import asyncio  # noqa: PLC0415

                    try:
                        if asyncio.iscoroutinefunction(check_fn):
                            met, detail = await check_fn()
                        else:
                            met, detail = check_fn()
                    except BridgeError as exc:
                        return tool_error_result(exc)
                    except Exception as exc:  # noqa: BLE001
                        logger.exception(
                            "Precondition '%s' check failed unexpectedly for %s",
                            name,
                            func.__name__,
                        )
                        return error_response(
                            f"Failed to evaluate precondition '{name}': {exc}",
                            transient=False,
                            error_code="PRECONDITION_CHECK_FAILED",
                            recovery_hint=(
                                "Inspect the server logs and current ConfigurationDesk state before retrying."
                            ),
                            next_action=(
                                "Call `get_application_status` or `diagnose_connection` to inspect the current environment before retrying."
                            ),
                            retryable=False,
                        )
                else:
                    met, detail = False, "Invalid precondition check."

                if not met:
                    error_msg = f"Precondition not met: {detail} {hint}"
                    logger.info(
                        "Precondition '%s' failed for %s: %s",
                        name,
                        func.__name__,
                        detail,
                    )
                    return json.dumps(
                        {
                            "success": False,
                            "error": error_msg,
                            "error_code": "PRECONDITION_NOT_MET",
                            "precondition": name,
                            "recovery_hint": hint,
                            "next_action": f"Call `{next_tool}` first.",
                            "retryable": False,
                        },
                        indent=2,
                    )

            return await func(*args, **kwargs)

        return wrapper

    return decorator
