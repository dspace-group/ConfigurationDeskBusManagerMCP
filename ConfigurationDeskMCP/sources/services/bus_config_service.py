# -*- coding: utf-8 -*-
"""Bus configuration service."""

from __future__ import annotations

from typing import List, Optional

from configurationdesk_com_bridge import dispatch, get_connection
from configurationdesk_com_bridge.domains import bus_config_com
from configurationdesk_com_bridge.errors import BridgeError

from sources.models.envelope_builder import tool_error_result
from sources.models.property_values import PropertyValue
from sources.services._observations import dispatch_observation
from sources.services._pagination import DEFAULT_PAGE_LIMIT, paginate
from sources.services.bus_element_properties import (
    resolve_property_name as resolve_bus_element_property_name,
    validate_property_value as validate_bus_element_property_value,
)
from sources.services._workflow_readiness import (
    require_application_process_ready,
)
from sources.tools._responses import error_response, success_response, unverified_response
from sources.utils.logger import get_logger
from sources.services.function_port_properties import (
    normalize_property_value,
    resolve_property_name,
    validate_property_value,
)

logger = get_logger(__name__)


async def create(name: Optional[str] = None) -> str:
    try:
        conn = get_connection()
        result = await dispatch(bus_config_com.create, conn, name)
        if result.get("verified"):
            return success_response(
                message=f"Bus configuration '{result['name']}' created",
                verified=True,
                name=result["name"],
            )
        return error_response(result.get("detail", "Creation failed"), transient=False)
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error creating bus configuration")
        return error_response(str(e), transient=False)


async def remove(name: str) -> str:
    try:
        conn = get_connection()
        result = await dispatch(bus_config_com.remove, conn, name)
        if result.get("verified"):
            return success_response(
                message="Bus configuration(s) removed", removed=result["removed"], verified=True
            )
        detail = result.get("detail", f"Still present: {result.get('still_present')}")
        return error_response(detail, transient=False)
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error removing bus configuration")
        return error_response(str(e), transient=False)


async def list_configs() -> str:
    try:
        conn = get_connection()
        configs = await dispatch_observation(bus_config_com.list_configs, conn)
        return success_response(bus_configurations=configs)
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error listing bus configurations")
        return error_response(str(e), transient=False)


async def assign_matrix(
    bus_config_name: str,
    element_name: Optional[str] = None,
    element_type: Optional[str] = None,
    matrix_xpath: Optional[str] = None,
    part: Optional[str] = None,
) -> str:
    try:
        conn = get_connection()
        result = await dispatch(
            bus_config_com.assign_matrix,
            conn,
            bus_config_name,
            element_name,
            element_type,
            matrix_xpath,
            part,
        )
        if result.get("error"):
            return error_response(result["detail"], transient=False)
        parts = result.get("parts") or []
        if result.get("verified"):
            return success_response(
                message="Matrix elements assigned",
                assigned=result["assigned"],
                parts=parts,
                verified=True,
            )
        return unverified_response(
            message="Assignment issued",
            assigned=result.get("assigned"),
            parts=parts,
        )
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error assigning matrix")
        return error_response(str(e), transient=False)


async def assign_ecu(
    bus_config_name: Optional[str] = None,
    ecu_names: Optional[List[str]] = None,
    ecu_xpath: Optional[str] = None,
    exclude_list: str = "",
    part: Optional[str] = None,
) -> str:
    try:
        conn = get_connection()
        result = await dispatch(
            bus_config_com.assign_ecu,
            conn,
            bus_config_name,
            ecu_names,
            ecu_xpath,
            exclude_list,
            part,
        )
        if result.get("error"):
            return error_response(result["detail"], transient=False)
        status = result.get("status", "")
        parts = result.get("parts") or []
        if status == "verified":
            return success_response(
                message="ECU(s) assigned",
                ecus=result["ecus"],
                parts=parts,
                verified=True,
            )
        return unverified_response(
            message="ECU assignment issued",
            ecus=result["ecus"],
            parts=parts,
        )
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error assigning ECU")
        return error_response(str(e), transient=False)


async def add_feature(
    feature_name: str,
    element_type: Optional[str] = None,
    element_name: Optional[str] = None,
    bus_config_name: Optional[str] = None,
    element_xpath: Optional[str] = None,
) -> str:
    try:
        conn = get_connection()
        result = await dispatch(
            bus_config_com.add_feature,
            conn,
            feature_name,
            element_type,
            element_name,
            bus_config_name,
            element_xpath,
        )
        if result.get("error"):
            detail = result["detail"]
            if "no elements found" in detail.lower():
                return error_response(
                    detail,
                    transient=False,
                    next_action=(
                        f"Element '{element_name or element_type}' not found in bus configurations. "
                        f"Ensure: 1) assign_ecu_to_bus_config was called first to populate the tree, "
                        f"2) The element_name matches a node name in the bus config (ECU name, cluster name, or config name). "
                        f"Use list_bus_access_requests to see what elements exist. Do NOT retry with the same parameters."
                    ),
                )
            if "available features" in detail.lower():
                return error_response(
                    detail,
                    transient=False,
                    next_action=(
                        f"Feature '{feature_name}' is not valid for the target element. "
                        f"The error shows available features — use one of those exact names. Do NOT retry with the same feature_name."
                    ),
                )
            return error_response(detail, transient=False)
        if result.get("verified"):
            return success_response(
                message=f"Feature '{feature_name}' added",
                elements=result["elements"],
                verified=True,
            )
        return unverified_response(
            message=f"Feature '{feature_name}' add issued", elements=result.get("elements")
        )
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error adding feature")
        return error_response(str(e), transient=False)


async def remove_elements(
    element_name: Optional[str] = None,
    element_type: Optional[str] = None,
    xpath: Optional[str] = None,
) -> str:
    try:
        conn = get_connection()
        result = await dispatch(
            bus_config_com.remove_elements, conn, element_name, element_type, xpath
        )
        if result.get("error"):
            return error_response(result["detail"], transient=False)
        if result.get("verified"):
            return success_response(
                message="Elements removed", removed=result["removed"], verified=True
            )
        return error_response(f"Still present: {result.get('still_present')}", transient=False)
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error removing elements")
        return error_response(str(e), transient=False)


async def generate_containers() -> str:
    try:
        conn = get_connection()
        await dispatch(bus_config_com.generate_containers, conn)
        return unverified_response(message="Container generation command issued")
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error generating containers")
        return error_response(str(e), transient=False)


async def find_elements(
    element_type: Optional[str] = None,
    element_name: Optional[str] = None,
    xpath: Optional[str] = None,
    offset: int = 0,
    limit: int = DEFAULT_PAGE_LIMIT,
) -> str:
    try:
        conn = get_connection()
        result = await dispatch_observation(
            bus_config_com.find_elements, conn, element_type, element_name, xpath
        )
        if result.get("error"):
            return error_response(result["detail"], transient=False)
        page = paginate(result["elements"], offset=offset, limit=limit)
        return success_response(elements=page.items, **page.response_metadata())
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error finding elements")
        return error_response(str(e), transient=False)


async def assign_to_application_process(
    bus_config_name: str, process_name: Optional[str] = None
) -> str:
    try:
        conn = get_connection()
        await require_application_process_ready(conn, process_name)
        result = await dispatch(
            bus_config_com.assign_to_application_process, conn, bus_config_name, process_name
        )
        if result.get("error"):
            return error_response(result["detail"], transient=False)
        if result.get("verified"):
            return success_response(
                message=f"Bus config '{bus_config_name}' assigned to process '{result['process']}'",
                verified=True,
            )
        return unverified_response(message="Assignment issued but could not verify")
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error assigning to application process")
        return error_response(str(e), transient=False)


async def set_function_port_property(
    property_name: str,
    value: PropertyValue,
    bus_config_name: Optional[str] = None,
    feature_type: Optional[str] = None,
    port_xpath: Optional[str] = None,
) -> str:
    try:
        canonical_name, alias_used = resolve_property_name(property_name)
        value = normalize_property_value(canonical_name, value)
        is_valid, type_error = validate_property_value(canonical_name, value)
        if not is_valid:
            return error_response(
                type_error,
                transient=False,
                error_code="INVALID_VALUE_TYPE",
                recovery_hint=(
                    "The value type does not match the property. Re-read the "
                    "error message for the expected type and example value."
                ),
                next_action=(
                    "Re-call set_function_port_property with the value rewritten "
                    "to the type shown in the error (e.g. 1.0 for a float "
                    "property, not true)."
                ),
            )
        conn = get_connection()
        result = await dispatch(
            bus_config_com.set_function_port_property,
            conn,
            canonical_name,
            value,
            bus_config_name,
            feature_type,
            port_xpath,
        )
        if result.get("error"):
            return error_response(
                result["detail"],
                transient=False,
                error_code=result.get("error_code", "BRIDGE_UNKNOWN"),
                recovery_hint=result.get("recovery_hint", ""),
                next_action=result.get("next_action", ""),
                retryable=result.get("retryable"),
            )
        if alias_used:
            message = (
                f"Property '{alias_used}' (resolved to '{canonical_name}') "
                f"set on {result['set_count']} port(s)"
            )
        else:
            message = f"Property '{canonical_name}' set on {result['set_count']} port(s)"
        return success_response(
            message=message,
            verified_count=result["verified_count"],
            mismatch_count=result["mismatch_count"],
        )
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error setting function port property")
        return error_response(str(e), transient=False)


async def set_bus_config_element_property(
    property_name: str,
    value: PropertyValue,
    element_name: Optional[str] = None,
    element_type: Optional[str] = None,
    xpath: Optional[str] = None,
    bus_config_name: Optional[str] = None,
    allow_multiple: bool = False,
) -> str:
    try:
        canonical_name, alias_used = resolve_bus_element_property_name(property_name)
        is_valid, type_error = validate_bus_element_property_value(
            canonical_name,
            value,
            scope="bus_config",
        )
        if not is_valid:
            return error_response(
                type_error,
                transient=False,
                error_code="INVALID_VALUE_TYPE",
                recovery_hint=(
                    "The value type does not match the selected bus configuration "
                    "element property. Re-read the error message for the expected "
                    "type and example value."
                ),
            )
        conn = get_connection()
        result = await dispatch(
            bus_config_com.set_bus_config_element_property,
            conn,
            canonical_name,
            value,
            element_name,
            element_type,
            xpath,
            bus_config_name,
            allow_multiple,
        )
        if result.get("error"):
            return error_response(result["detail"], transient=False)

        actual_name = result.get("property_name", canonical_name)
        if alias_used:
            message = (
                f"Property '{alias_used}' (resolved to '{actual_name}') set on "
                f"{result['set_count']} bus configuration element(s)"
            )
        else:
            message = f"Property '{actual_name}' set on {result['set_count']} bus configuration element(s)"
        return success_response(
            message=message,
            elements=result.get("elements", []),
            verified_count=result.get("verified_count", 0),
            mismatch_count=result.get("mismatch_count", 0),
            xpath_used=result.get("xpath_used"),
        )
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error setting bus configuration element property")
        return error_response(str(e), transient=False)
