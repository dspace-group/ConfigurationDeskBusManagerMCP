# -*- coding: utf-8 -*-
"""Bus access service."""

from __future__ import annotations

from typing import Optional

from configurationdesk_com_bridge import dispatch, get_connection
from configurationdesk_com_bridge.domains import bus_access_com
from configurationdesk_com_bridge.errors import BridgeError

from sources.models.envelope_builder import tool_error_result
from sources.services._observations import dispatch_observation
from sources.services._pagination import DEFAULT_PAGE_LIMIT, paginate
from sources.services._workflow_readiness import (
    require_application_process_ready,
    require_hardware_topology_ready,
    require_model_ready,
)
from sources.tools._responses import error_response, success_response, unverified_response
from sources.utils.logger import get_logger

logger = get_logger(__name__)

_BUS_FB_TYPES = {"CAN", "LIN", "Ethernet"}


async def create_bus_function_block(name: str, bus_type: str = "CAN") -> str:
    if bus_type not in _BUS_FB_TYPES:
        return error_response(
            f"Unsupported bus_type '{bus_type}'. Use one of: {sorted(_BUS_FB_TYPES)}",
            transient=False,
        )
    try:
        conn = get_connection()
        result = await dispatch(bus_access_com.create_bus_function_block, conn, name, bus_type)
        if result.get("verified"):
            return success_response(
                message=f"{bus_type} function block '{name}' created",
                name=name,
                bus_type=bus_type,
                properties=result.get("properties"),
                verified=True,
            )
        return unverified_response(
            message=f"{bus_type} function block '{name}' creation issued but could not verify",
            name=name,
            bus_type=bus_type,
            properties=result.get("properties"),
        )
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error creating bus function block")
        return error_response(str(e), transient=False)


async def set_bus_function_block_property(
    function_block_name: str, property_name: str, value: str, bus_type: str = "CAN"
) -> str:
    if bus_type not in _BUS_FB_TYPES:
        return error_response(
            f"Unsupported bus_type '{bus_type}'. Use one of: {sorted(_BUS_FB_TYPES)}",
            transient=False,
            next_action="Fix the bus_type parameter. Valid values: 'CAN', 'LIN', 'Ethernet'.",
        )
    try:
        conn = get_connection()
        result = await dispatch(
            bus_access_com.set_bus_function_block_property,
            conn,
            function_block_name,
            property_name,
            value,
            bus_type,
        )
        if result.get("error"):
            detail = result["detail"]
            if "not found" in detail.lower():
                return error_response(
                    detail,
                    transient=False,
                    next_action=(
                        f"Function block '{function_block_name}' was not found. "
                        f"Verify it was created with create_io_function_block. "
                        f"If the block is LIN, pass bus_type='LIN'. Current bus_type='{bus_type}'."
                    ),
                )
            return error_response(detail, transient=False)
        if result.get("verified"):
            return success_response(
                message=f"Property '{property_name}' set to {result['value_set']} on '{function_block_name}'",
                property_name=property_name,
                value=result["value_set"],
                value_readback=result.get("value_readback"),
                verified=True,
            )
        return unverified_response(
            message="Property set but read-back mismatch",
            property_name=property_name,
            value_set=result.get("value_set"),
            value_readback=result.get("value_readback"),
        )
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error setting function block property")
        return error_response(str(e), transient=False)


async def list_bus_function_block_properties(
    function_block_name: str, bus_type: str = "CAN"
) -> str:
    if bus_type not in _BUS_FB_TYPES:
        return error_response(
            f"Unsupported bus_type '{bus_type}'. Use one of: {sorted(_BUS_FB_TYPES)}",
            transient=False,
        )
    try:
        conn = get_connection()
        result = await dispatch_observation(
            bus_access_com.list_bus_function_block_properties, conn, function_block_name, bus_type
        )
        if result.get("error"):
            return error_response(result["detail"], transient=False)
        return success_response(
            function_block=function_block_name,
            bus_type=bus_type,
            properties=result["properties"],
            count=result["count"],
        )
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error listing function block properties")
        return error_response(str(e), transient=False)


async def list_bus_access_requests(
    bus_config_name: Optional[str] = None,
    offset: int = 0,
    limit: int = DEFAULT_PAGE_LIMIT,
) -> str:
    try:
        conn = get_connection()
        result = await dispatch_observation(
            bus_access_com.list_bus_access_requests, conn, bus_config_name
        )
        page = paginate(result["requests"], offset=offset, limit=limit)
        return success_response(requests=page.items, **page.response_metadata())
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error listing bus access requests")
        return error_response(str(e), transient=False)


async def assign_bus_access(
    function_block_name: str,
    bus_config_name: Optional[str] = None,
    cluster_name: Optional[str] = None,
) -> str:
    try:
        conn = get_connection()
        result = await dispatch(
            bus_access_com.assign_bus_access,
            conn,
            function_block_name,
            bus_config_name,
            cluster_name,
        )
        if result.get("error"):
            return error_response(result["detail"], transient=False)
        if result.get("verified"):
            return success_response(
                message=f"Assigned bus access to '{function_block_name}'",
                assigned_configs=result["assigned_configs"],
                verified=True,
                verified_count=result["verified_count"],
            )
        return unverified_response(
            message="Set bus access on request(s) but could not verify",
            assigned_configs=result.get("assigned_configs"),
        )
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error assigning bus access")
        return error_response(str(e), transient=False)


async def list_assignable_channel_sets(function_block_name: str, bus_type: str = "CAN") -> str:
    if bus_type not in _BUS_FB_TYPES:
        return error_response(
            f"Unsupported bus_type '{bus_type}'. Use one of: {sorted(_BUS_FB_TYPES)}",
            transient=False,
        )
    try:
        conn = get_connection()
        await require_hardware_topology_ready(conn)
        result = await dispatch_observation(
            bus_access_com.list_assignable_channel_sets, conn, function_block_name, bus_type
        )
        if result.get("error"):
            return error_response(result["detail"], transient=False)
        return success_response(
            function_block=function_block_name,
            channel_sets=result["channel_sets"],
            count=result["count"],
        )
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error listing assignable channel sets")
        return error_response(str(e), transient=False)


async def assign_channel_set(
    function_block_name: str, channel_set_index: int = 0, bus_type: str = "CAN"
) -> str:
    if bus_type not in _BUS_FB_TYPES:
        return error_response(
            f"Unsupported bus_type '{bus_type}'. Use one of: {sorted(_BUS_FB_TYPES)}",
            transient=False,
        )
    try:
        conn = get_connection()
        await require_hardware_topology_ready(conn)
        result = await dispatch(
            bus_access_com.assign_channel_set,
            conn,
            function_block_name,
            channel_set_index,
            bus_type,
        )
        if result.get("error"):
            return error_response(result["detail"], transient=False)
        return success_response(
            message=f"Channel set '{result['channel_set']}' assigned to '{function_block_name}'",
            function_block=function_block_name,
            channel_set=result["channel_set"],
            channel_set_index=channel_set_index,
            verified=True,
        )
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error assigning channel set")
        return error_response(str(e), transient=False)


async def auto_assign_channel_set(function_block_name: str, bus_type: str = "CAN") -> str:
    if bus_type not in _BUS_FB_TYPES:
        return error_response(
            f"Unsupported bus_type '{bus_type}'. Use one of: {sorted(_BUS_FB_TYPES)}",
            transient=False,
            next_action="Fix the bus_type parameter. Valid values: 'CAN', 'LIN', 'Ethernet'.",
        )
    try:
        conn = get_connection()
        await require_hardware_topology_ready(conn)
        result = await dispatch(
            bus_access_com.auto_assign_channel_set, conn, function_block_name, bus_type
        )
        if result.get("error"):
            detail = result["detail"]
            if "not found" in detail.lower():
                return error_response(
                    detail,
                    transient=False,
                    next_action=(
                        f"Function block '{function_block_name}' not found. "
                        f"Verify it exists with list_io_function_block_properties. "
                        f"If the block is LIN, pass bus_type='LIN'. "
                        f"Also ensure a hardware topology exists (add_hardware_platform or import_hardware_topology), or add a processing unit application (add_processing_unit_application) for a no-hardware build."
                    ),
                )
            return error_response(detail, transient=False)
        return success_response(
            message=f"Channel set auto-assigned to '{function_block_name}'",
            function_block=function_block_name,
            verified=True,
        )
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error auto-assigning channel set")
        return error_response(str(e), transient=False)


async def assign_hardware_automatically() -> str:
    try:
        conn = get_connection()
        await require_hardware_topology_ready(conn)
        result = await dispatch(bus_access_com.assign_hardware_automatically, conn)
        if result.get("error"):
            return error_response(result["detail"], transient=False)
        if result.get("verified"):
            payload = dict(result)
            payload.pop("verified", None)
            return success_response(
                message="Hardware automatically assigned to all I/O function blocks",
                verified=True,
                **payload,
            )
        return error_response(
            result.get(
                "detail",
                "Automatic hardware assignment completed without a verifiable channel assignment.",
            ),
            transient=False,
            next_action=(
                "Use `list_assignable_channel_sets` and `assign_channel_set`, or "
                "`auto_assign_channel_set`, to complete the assignment explicitly."
            ),
        )
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error in automatic hardware assignment")
        return error_response(str(e), transient=False)


async def auto_connect_matching_io_function_blocks_to_model_ports() -> str:
    try:
        conn = get_connection()
        await require_model_ready(conn)
        await require_application_process_ready(conn)
        result = await dispatch(
            bus_access_com.auto_connect_matching_io_function_blocks_to_model_ports,
            conn,
        )
        if result.get("error"):
            return error_response(
                result["detail"],
                transient=False,
                next_action=(
                    "Auto-connect failed. "
                    "Ensure: 1) at least one I/O function block exists (create_io_function_block), "
                    "2) a model is added and analyzed, "
                    "3) the matching model ports are in the signal chain "
                    "(add_model_to_signal_chain or add_model_port_to_signal_chain). "
                    "Do NOT retry with the same parameters."
                ),
            )
        if result.get("verified"):
            return success_response(
                message="Matching I/O function block ports connected to model ports",
                verified=True,
                function_blocks=result.get("function_blocks"),
                links_before=result.get("links_before"),
                links_after=result.get("links_after"),
                new_links=result.get("new_links"),
            )
        return error_response(
            result.get(
                "detail",
                "Auto-connect command completed, but no new links became observable.",
            ),
            transient=False,
            next_action=(
                "Verify that the I/O function block port names match the model port names, "
                "or connect ports manually in ConfigurationDesk."
            ),
        )
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error auto-connecting IO function blocks to model ports")
        return error_response(str(e), transient=False)


# Backwards compatibility alias.
connect_io_function_blocks_to_model_ports = auto_connect_matching_io_function_blocks_to_model_ports


async def create_preconfigured_application_process(model_name: str) -> str:
    try:
        conn = get_connection()
        await require_model_ready(conn, model_name)
        result = await dispatch(
            bus_access_com.create_preconfigured_application_process,
            conn,
            model_name,
        )
        if result.get("error"):
            return error_response(
                result["detail"],
                transient=False,
                next_action=(
                    "Pre-configured application process creation failed. "
                    "Verify the model exists in the topology and a ProcessingUnitApplication "
                    "is available (registered hardware or `add_processing_unit_application`). "
                    "Do NOT retry with the same parameters."
                ),
            )
        if result.get("verified"):
            payload = dict(result)
            payload.pop("verified", None)
            return success_response(
                message=f"Pre-configured application process created for model '{model_name}'",
                verified=True,
                **payload,
            )
        return error_response(
            "No new application process became observable after the pre-configured creation call.",
            transient=False,
            next_action=(
                "Verify a ProcessingUnitApplication exists (use `add_processing_unit_application` "
                "for VEOS workflows, or register hardware). Then call `create_application_process` "
                "as the manual fallback."
            ),
        )
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error creating pre-configured application process")
        return error_response(
            str(e),
            transient=False,
            next_action=(
                "Pre-configured application process creation failed. "
                "Try create_application_process instead (alternative API). Do NOT retry this call."
            ),
        )
