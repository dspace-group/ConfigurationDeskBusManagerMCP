# -*- coding: utf-8 -*-
"""Application management service."""

from __future__ import annotations

from configurationdesk_com_bridge import dispatch, ensure_connected, get_connection
from configurationdesk_com_bridge.domains import app_management_com
from configurationdesk_com_bridge.errors import BridgeError

from sources.models.envelope_builder import tool_error_result
from sources.services._observations import dispatch_observation
from sources.tools._responses import error_response, success_response
from sources.utils.logger import get_logger

logger = get_logger(__name__)


async def _get_live_connection():
    """Return a connected COM bridge, auto-connecting if needed."""
    conn = get_connection()
    if not conn.is_connected:
        logger.info("Connection not active — calling ensure_connected()")
        await ensure_connected()
        conn = get_connection()
    return conn


async def add_application(name: str) -> str:
    try:
        conn = await _get_live_connection()
        result = await dispatch(app_management_com.add_application, conn, name)
        if result.get("verified"):
            return success_response(
                message=f"Application '{result['name']}' added", name=result["name"], verified=True
            )
        return error_response(result.get("detail", "Add application failed"), transient=False)
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error adding application")
        return error_response(str(e), transient=False)


async def activate_application(name: str) -> str:
    try:
        conn = await _get_live_connection()
        result = await dispatch(app_management_com.activate_application, conn, name)
        if result.get("verified"):
            return success_response(message=f"Application '{name}' activated", verified=True)
        return error_response(result.get("detail", "Activation failed"), transient=False)
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error activating application")
        return error_response(str(e), transient=False)


async def remove_application(name: str) -> str:
    try:
        conn = await _get_live_connection()
        result = await dispatch(
            app_management_com.remove_application, conn, name, timeout_ms=120000
        )
        if result.get("verified"):
            return success_response(message=f"Application '{name}' removed", verified=True)
        return error_response(result.get("detail", "Removal failed"), transient=False)
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error removing application")
        return error_response(str(e), transient=False)


async def list_applications() -> str:
    try:
        conn = get_connection()
        apps = await dispatch_observation(app_management_com.list_applications, conn)
        return success_response(applications=apps)
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error listing applications")
        return error_response(str(e), transient=False)


async def add_processing_unit_application() -> str:
    """Add a processing unit application to the executable application.

    A processing unit application hosts one or more application processes. Add one
    explicitly when no registered hardware or imported topology already provides
    one — typically a no-hardware or VEOS build.
    """
    try:
        conn = await _get_live_connection()
        result = await dispatch(app_management_com.add_processing_unit_application, conn)
        pu_created = result.get("processing_unit_created", False)
        if not pu_created:
            return error_response(
                f"ProcessingUnitApplication could not be added: {result.get('processing_unit_detail', '')}. "
                "You may need to add it manually in ConfigurationDesk.",
                transient=False,
            )
        return success_response(
            message=(
                "ProcessingUnitApplication added. "
                "For VEOS: use generate_bus_containers to produce BSC files."
            ),
            verified=True,
        )
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error adding processing unit application")
        return error_response(str(e), transient=False)
