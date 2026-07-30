# -*- coding: utf-8 -*-
"""Build management service."""

from __future__ import annotations

from configurationdesk_com_bridge import dispatch, get_connection
from configurationdesk_com_bridge.domains import build_com
from configurationdesk_com_bridge.errors import BridgeError

from sources.models.envelope_builder import tool_error_result
from sources.services._observations import dispatch_observation
from sources.services._workflow_readiness import require_hardware_topology_ready
from sources.tools._responses import error_response, success_response
from sources.utils.logger import get_logger

logger = get_logger(__name__)


async def build_application(download: bool = True, start: bool = True, unload: bool = True) -> str:
    try:
        conn = get_connection()
        if download:
            await require_hardware_topology_ready(conn)
        result = await dispatch(
            build_com.build_application,
            conn,
            download,
            start,
            unload,
            timeout_ms=600000,
        )
        if result.get("success"):
            return success_response(
                message="Build successful",
                result_folder=result.get("result_folder"),
                rta_path=result.get("rta_path"),
            )
        if result.get("canceled"):
            return error_response(
                "Build canceled",
                transient=False,
                recovery_hint=(
                    "Inspect the current build state before deciding whether to run another build."
                ),
                next_action=(
                    "Do NOT retry automatically. Rerun `build_application` only after the user chooses to do so."
                ),
            )
        return error_response("Build failed", transient=False)
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error building application")
        return error_response(str(e), transient=False)


async def get_build_result() -> str:
    try:
        conn = get_connection()
        path = await dispatch_observation(build_com.get_build_result, conn)
        return success_response(path=path)
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error getting build result")
        return error_response(str(e), transient=False)
