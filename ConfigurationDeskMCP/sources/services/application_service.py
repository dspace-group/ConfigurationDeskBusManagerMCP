# -*- coding: utf-8 -*-
"""Application lifecycle service."""

from __future__ import annotations

from configurationdesk_com_bridge import dispatch, ensure_connected, get_connection
from configurationdesk_com_bridge.domains import application_com
from configurationdesk_com_bridge.errors import BridgeError

from sources.models.envelope_builder import tool_error_result
from sources.services._observations import dispatch_observation
from sources.tools._responses import error_response, success_response, unverified_response
from sources.utils.logger import get_logger

logger = get_logger(__name__)


def _inspect_connection(connection) -> dict[str, object]:
    """Read bridge health on the STA thread without changing connection state."""
    return {
        "connection_state": connection.state.value,
        "health_check": connection.health_check(),
    }


async def start(visible: bool = True) -> str:
    try:
        await ensure_connected(visible=visible)
        return success_response(message="ConfigurationDesk started successfully")
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error starting ConfigurationDesk")
        return error_response(str(e), transient=True)


async def stop(save: bool = True) -> str:
    try:
        conn = get_connection()
        result = await dispatch(conn.disconnect, save)
        if result:
            return success_response(message="ConfigurationDesk closed")
        return error_response("Failed to close ConfigurationDesk", transient=False)
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error stopping ConfigurationDesk")
        return error_response(str(e), transient=False)


async def get_status() -> str:
    try:
        conn = get_connection()
        status = await dispatch_observation(application_com.get_status, conn)
        return success_response(**status)
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error getting status")
        return error_response(str(e), transient=False)


async def save_project() -> str:
    try:
        conn = get_connection()
        result = await dispatch(application_com.save_project, conn)
        if result.get("verified"):
            return success_response(message="Project saved", verified=True)
        return unverified_response(message="Save command issued")
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error saving project")
        return error_response(str(e), transient=False)


async def undo() -> str:
    try:
        conn = get_connection()
        await dispatch(application_com.undo, conn)
        return success_response(message="Undo executed")
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error executing undo")
        return error_response(str(e), transient=False)


async def redo() -> str:
    try:
        conn = get_connection()
        await dispatch(application_com.redo, conn)
        return success_response(message="Redo executed")
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error executing redo")
        return error_response(str(e), transient=False)


async def diagnose_connection() -> str:
    """Run diagnostics on the COM connection environment.

    Checks: pywin32 availability, COM registration, running instance,
    dynamic dispatch capability, and current bridge state.
    Returns a structured report with pass/fail for each check.
    """
    diagnostics: dict[str, object] = {}

    # 1. Check pywin32 availability
    try:
        import win32com.client  # noqa: PLC0415

        diagnostics["pywin32_installed"] = True
    except ImportError:
        diagnostics["pywin32_installed"] = False
        return success_response(
            diagnostics=diagnostics,
            summary="pywin32 is not installed. Install it with: pip install pywin32",
            next_action="Install pywin32 and restart the server.",
        )

    # 2. Check bridge state
    try:
        conn = get_connection()
        diagnostics["bridge_started"] = True
        health = await dispatch_observation(_inspect_connection, conn)
        diagnostics.update(health)
    except BridgeError:
        diagnostics["connection_state"] = conn.state.value
        diagnostics["health_check"] = False
    except RuntimeError:
        diagnostics["bridge_started"] = False
        diagnostics["connection_state"] = "NOT_INITIALIZED"
        diagnostics["health_check"] = False

    # 3. Check if ConfigurationDesk is registered in COM
    product_id = "ConfigurationDesk.Application"
    try:
        import winreg  # noqa: PLC0415

        key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, product_id + "\\CLSID")
        clsid, _ = winreg.QueryValueEx(key, "")
        winreg.CloseKey(key)
        diagnostics["com_registered"] = True
        diagnostics["clsid"] = clsid
    except (OSError, FileNotFoundError):
        diagnostics["com_registered"] = False
        diagnostics["clsid"] = None

    # 4. Check for running instance
    try:
        win32com.client.GetActiveObject(product_id)
        diagnostics["running_instance"] = True
    except Exception:
        diagnostics["running_instance"] = False

    # 5. Check dynamic dispatch capability
    if not diagnostics.get("running_instance"):
        try:
            import win32com.client.dynamic  # noqa: PLC0415

            diagnostics["dynamic_dispatch_available"] = True
        except ImportError:
            diagnostics["dynamic_dispatch_available"] = False

    # Build summary
    issues = []
    if not diagnostics.get("com_registered"):
        issues.append("ConfigurationDesk is NOT registered in COM — it may not be installed.")
    if not diagnostics.get("bridge_started"):
        issues.append("COM bridge not initialized — call start_configurationdesk.")
    if diagnostics.get("bridge_started") and not diagnostics.get("health_check"):
        issues.append(
            "COM connection exists but health check failed — the process may have crashed."
        )

    summary = " | ".join(issues) if issues else "All checks passed. Connection appears healthy."

    return success_response(diagnostics=diagnostics, summary=summary)
