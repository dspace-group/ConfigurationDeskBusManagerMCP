# -*- coding: utf-8 -*-
"""Hardware management service."""

from __future__ import annotations

from configurationdesk_com_bridge import dispatch, get_connection
from configurationdesk_com_bridge.domains import hardware_com
from configurationdesk_com_bridge.errors import BridgeError

from sources.models.envelope_builder import tool_error_result
from sources.services._observations import dispatch_observation
from sources.tools._responses import error_response, success_response
from sources.utils.logger import get_logger

logger = get_logger(__name__)


async def add_hardware_platform(ip_addresses: list[str], platform_type: str = "SCALEXIO") -> str:
    try:
        conn = get_connection()
        result = await dispatch(
            hardware_com.add_hardware_platform, conn, ip_addresses, platform_type
        )
        if result.get("error"):
            return error_response(
                result["detail"],
                transient=False,
                retryable=False,
                next_action=(
                    "VEOS is not a registered real-time hardware platform. For VEOS workflows: "
                    "1) Use generate_bus_containers to create BSC files, "
                    "2) Import BSC files into VEOS. "
                    "For SCALEXIO: ensure hardware is powered on and reachable."
                )
                if platform_type.upper() == "VEOS"
                else (
                    f"Platform registration failed for '{platform_type}'. "
                    f"Ensure SCALEXIO hardware is powered on and reachable at the specified IP."
                ),
            )
        platform_name = result.get("platform_name", "")
        if not result.get("verified"):
            return error_response(
                f"Hardware platform '{platform_name}' was registered, but no hardware topology items became visible.",
                transient=False,
            )
        return success_response(
            message=f"Hardware platform '{platform_name}' registered and scanned",
            platform_name=platform_name,
            hardware_items=result.get("hardware_items", []),
            verified=True,
        )
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error adding hardware platform")
        return error_response(str(e), transient=False)


async def import_hardware_topology(path: str) -> str:
    try:
        conn = get_connection()
        result = await dispatch(hardware_com.import_hardware_topology, conn, path)
        if result.get("verified"):
            payload = dict(result)
            payload.pop("verified", None)
            return success_response(
                message="Hardware topology imported",
                verified=True,
                **payload,
            )
        return error_response(result.get("detail", "Import failed"), transient=False)
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error importing hardware topology")
        return error_response(str(e), transient=False)


async def scan_hardware(platform_name: str) -> str:
    try:
        conn = get_connection()
        result = await dispatch(hardware_com.scan_hardware, conn, platform_name)
        if not result.get("verified"):
            return error_response(
                f"Hardware scan completed for '{platform_name}', but no hardware topology items became visible.",
                transient=False,
            )
        return success_response(
            message=f"Hardware scan completed for '{platform_name}'",
            platform_name=platform_name,
            hardware_items=result.get("hardware_items", []),
            verified=result.get("verified", False),
        )
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error scanning hardware")
        return error_response(str(e), transient=False)


async def remove_hardware(name: str) -> str:
    try:
        conn = get_connection()
        result = await dispatch(hardware_com.remove_hardware, conn, name)
        if result.get("verified"):
            return success_response(message=f"Hardware '{name}' removed", verified=True)
        return error_response(result.get("detail", "Removal failed"), transient=False)
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error removing hardware")
        return error_response(str(e), transient=False)


async def list_platforms() -> str:
    try:
        conn = get_connection()
        platforms = await dispatch_observation(hardware_com.list_platforms, conn)
        return success_response(platforms=platforms)
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error listing platforms")
        return error_response(str(e), transient=False)


async def refresh_platforms() -> str:
    try:
        conn = get_connection()
        result = await dispatch(hardware_com.refresh_platforms, conn)
        return success_response(message="Platforms refreshed", **result)
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error refreshing platforms")
        return error_response(str(e), transient=False)


async def add_hardware_element(element_type: str) -> str:
    try:
        conn = get_connection()
        result = await dispatch(hardware_com.add_hardware_element, conn, element_type)
        if result.get("error"):
            return error_response(result["detail"], transient=False)
        if not result.get("verified"):
            return error_response(
                f"Hardware element '{result.get('element_name', element_type)}' was created but did not become observable.",
                transient=False,
            )
        payload = dict(result)
        payload.pop("verified", None)
        return success_response(
            message=f"Hardware element '{result.get('element_name', element_type)}' added",
            verified=True,
            **payload,
        )
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error adding hardware element")
        return error_response(str(e), transient=False)
