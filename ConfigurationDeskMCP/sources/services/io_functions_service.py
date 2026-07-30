# -*- coding: utf-8 -*-
"""I/O Functions Library service."""

from __future__ import annotations

from configurationdesk_com_bridge import dispatch, get_connection
from configurationdesk_com_bridge.domains import io_functions_com
from configurationdesk_com_bridge.errors import BridgeError

from sources.models.envelope_builder import tool_error_result
from sources.services._observations import dispatch_observation
from sources.tools._responses import error_response, success_response, unverified_response
from sources.utils.logger import get_logger

logger = get_logger(__name__)


async def add_io_function_block(function_type_name: str, block_name: str) -> str:
    try:
        conn = get_connection()
        result = await dispatch(
            io_functions_com.add_io_function_block,
            conn,
            function_type_name,
            block_name,
        )
        if result.get("error"):
            detail = result["detail"]
            if "not found" in detail.lower():
                return error_response(
                    detail,
                    transient=False,
                    next_action=(
                        "Call `list_io_function_block_types` to discover valid "
                        "function_type_name values, then retry with a correct name."
                    ),
                )
            return error_response(detail, transient=False)
        if result.get("verified"):
            return success_response(
                message=(
                    f"I/O function block '{block_name}' of type "
                    f"'{function_type_name}' added to signal chain"
                ),
                name=block_name,
                function_type=function_type_name,
                properties=result.get("properties"),
                verified=True,
            )
        return unverified_response(
            message=(f"I/O function block '{block_name}' creation issued but could not verify"),
            name=block_name,
            function_type=function_type_name,
            properties=result.get("properties"),
        )
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error adding I/O function block")
        return error_response(str(e), transient=False)


async def list_io_function_block_types() -> str:
    try:
        conn = get_connection()
        result = await dispatch_observation(io_functions_com.list_io_function_block_types, conn)
        if result.get("error"):
            return error_response(result["detail"], transient=False)
        return success_response(
            types=result["types"],
            count=result["count"],
        )
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error listing I/O function block types")
        return error_response(str(e), transient=False)


async def connect_function_block_port_to_model_port(
    function_block_name: str,
    function_block_port_name: str,
    model_name: str,
    model_port_name: str,
) -> str:
    try:
        conn = get_connection()
        result = await dispatch(
            io_functions_com.connect_function_block_port_to_model_port,
            conn,
            function_block_name,
            function_block_port_name,
            model_name,
            model_port_name,
        )
        if result.get("error"):
            detail = result["detail"]
            low = detail.lower()
            if "function block" in low and "not found" in low:
                return error_response(
                    detail,
                    transient=False,
                    next_action=(
                        "Verify the function block name is spelled correctly and exists "
                        "in the signal chain. If it does not exist, create it with "
                        "`add_io_function_block` (analog/digital I/O) or "
                        "`create_io_function_block` (CAN/LIN/Ethernet bus)."
                    ),
                )
            if "model port block" in low and "not found" in low:
                return error_response(
                    detail,
                    transient=False,
                    next_action=(
                        "Call `list_model_ports` with the given model_name to "
                        "discover valid model port names."
                    ),
                )
            if "model '" in low and "not found" in low:
                return error_response(
                    detail,
                    transient=False,
                    next_action=("Add the model first with `add_model`, then retry."),
                )
            return error_response(detail, transient=False)

        message = (
            f"Connected '{function_block_name}.{function_block_port_name}' "
            f"to '{model_name}.{model_port_name}'"
        )
        if result.get("verified"):
            return success_response(
                message=message,
                verified=True,
                function_block_name=function_block_name,
                function_block_port_name=function_block_port_name,
                model_name=model_name,
                model_port_name=model_port_name,
            )
        return unverified_response(
            message=message + " (issued but could not verify Links)",
            function_block_name=function_block_name,
            function_block_port_name=function_block_port_name,
            model_name=model_name,
            model_port_name=model_port_name,
        )
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error connecting function block port to model port")
        return error_response(str(e), transient=False)
