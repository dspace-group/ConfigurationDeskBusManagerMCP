# -*- coding: utf-8 -*-
"""Working view and conflict service."""

from __future__ import annotations

from configurationdesk_com_bridge import dispatch, get_connection
from configurationdesk_com_bridge.domains import working_view_com
from configurationdesk_com_bridge.errors import BridgeError

from sources.models.envelope_builder import tool_error_result
from sources.services._observations import dispatch_observation
from sources.tools._responses import error_response, success_response
from sources.utils.logger import get_logger

logger = get_logger(__name__)


async def create_working_view(name: str) -> str:
    try:
        conn = get_connection()
        result = await dispatch(working_view_com.create_working_view, conn, name)
        if result.get("verified"):
            return success_response(message=f"Working view created: {name}", verified=True)
        return error_response(
            f"Working view creation issued but '{name}' not verified", transient=False
        )
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error creating working view")
        return error_response(str(e), transient=False)


async def list_working_views() -> str:
    try:
        conn = get_connection()
        views = await dispatch_observation(working_view_com.list_working_views, conn)
        return success_response(working_views=views)
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error listing working views")
        return error_response(str(e), transient=False)


async def remove_working_view(name: str) -> str:
    try:
        conn = get_connection()
        result = await dispatch(working_view_com.remove_working_view, conn, name)
        if result.get("error"):
            return error_response(result["detail"], transient=False)
        if result.get("verified"):
            return success_response(message=f"Working view removed: {name}", verified=True)
        return error_response(
            f"Working view removal issued but '{name}' was not confirmed",
            transient=False,
        )
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error removing working view")
        return error_response(str(e), transient=False)


async def clear_all_working_views() -> str:
    try:
        conn = get_connection()
        result = await dispatch(working_view_com.clear_all_working_views, conn)
        if result.get("verified"):
            return success_response(message="All working views cleared", verified=True)
        return error_response(
            f"Clear command issued but {result.get('remaining')} working view(s) remain",
            transient=False,
        )
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error clearing working views")
        return error_response(str(e), transient=False)


async def export_working_view(name: str, path: str) -> str:
    try:
        conn = get_connection()
        result = await dispatch(working_view_com.export_working_view, conn, name, path)
        if result.get("error"):
            return error_response(result["detail"], transient=False)
        if result.get("verified"):
            return success_response(
                message=f"Working view '{name}' exported to '{result['path']}'",
                path=result["path"],
                verified=True,
            )
        return error_response("Export command issued but file not found", transient=False)
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error exporting working view")
        return error_response(str(e), transient=False)


async def check_conflicts() -> str:
    try:
        conn = get_connection()
        result = await dispatch_observation(working_view_com.check_conflicts, conn)
        return success_response(conflicts=result["conflicts"], count=result["count"])
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error checking conflicts")
        return error_response(str(e), transient=False)
