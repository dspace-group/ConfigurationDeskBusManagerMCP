# -*- coding: utf-8 -*-
"""Communication matrix service."""

from __future__ import annotations

from typing import Optional

from configurationdesk_com_bridge import dispatch, get_connection
from configurationdesk_com_bridge.domains import matrix_com
from configurationdesk_com_bridge.errors import BridgeError

from sources.models.envelope_builder import tool_error_result
from sources.models.property_values import PropertyValue
from sources.services._observations import dispatch_observation
from sources.services._pagination import DEFAULT_PAGE_LIMIT, paginate
from sources.services.bus_element_properties import (
    resolve_property_name as resolve_bus_element_property_name,
    validate_property_value as validate_bus_element_property_value,
)
from sources.tools._responses import error_response, success_response
from sources.utils.logger import get_logger

logger = get_logger(__name__)


async def add_communication_matrix(path: str) -> str:
    try:
        conn = get_connection()
        result = await dispatch(matrix_com.add_communication_matrix, conn, path)
        if result.get("verified"):
            return success_response(
                message=f"Communication matrix added: {result['path']}",
                verified=True,
                new_clusters=result["new_clusters"],
                new_ecus=result["new_ecus"],
            )
        return error_response(
            f"COM call completed but no new matrix entries appeared after adding '{path}'",
            transient=False,
        )
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error adding communication matrix")
        return error_response(str(e), transient=False)


async def remove_communication_matrix(
    name: Optional[str] = None, xpath: Optional[str] = None, force: bool = False
) -> str:
    try:
        conn = get_connection()
        result = await dispatch(matrix_com.remove_communication_matrix, conn, name, xpath, force)
        if result.get("error"):
            return error_response(result["detail"], transient=False)
        if result.get("verified"):
            return success_response(
                message=f"{len(result['removed'])} matrix element(s) removed",
                removed=result["removed"],
                verified=True,
            )
        return error_response(
            f"Removal issued but still present: {result.get('still_present')}",
            transient=False,
        )
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error removing communication matrix")
        return error_response(str(e), transient=False)


async def list_matrices(offset: int = 0, limit: int = DEFAULT_PAGE_LIMIT) -> str:
    try:
        conn = get_connection()
        result = await dispatch_observation(matrix_com.list_matrices, conn)
        pages = {
            view: paginate(entries, offset=offset, limit=limit)
            for view, entries in result["matrices"].items()
        }
        total_count = sum(page.total_count for page in pages.values())
        return success_response(
            matrices={view: page.items for view, page in pages.items()},
            view_counts={view: page.total_count for view, page in pages.items()},
            count=total_count,
            total_count=total_count,
            returned_count=sum(len(page.items) for page in pages.values()),
            offset=offset,
            limit=limit,
            next_offset=(
                offset + limit
                if any(page.next_offset is not None for page in pages.values())
                else None
            ),
        )
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error listing matrices")
        return error_response(str(e), transient=False)


async def find_matrix_elements(
    element_type: Optional[str] = None,
    element_name: Optional[str] = None,
    xpath: Optional[str] = None,
    view: str = "clusters",
    offset: int = 0,
    limit: int = DEFAULT_PAGE_LIMIT,
) -> str:
    try:
        conn = get_connection()
        result = await dispatch_observation(
            matrix_com.find_matrix_elements, conn, element_type, element_name, xpath, view
        )
        if result.get("error"):
            return error_response(
                result["detail"],
                transient=False,
                next_action="Provide at least one of: element_type ('cluster', 'ecu', 'pdu', 'frame', 'signal'), element_name, or xpath.",
            )
        page = paginate(result["elements"], offset=offset, limit=limit)
        if result["count"] == 0:
            return success_response(
                elements=page.items,
                message=(
                    f"No elements found for type='{element_type}', name='{element_name}'. "
                    f"This may mean the communication matrix has not been loaded yet "
                    f"(call add_communication_matrix first) or the element type name differs. "
                    f"Try view='ecus' or a different element_type."
                ),
                xpath_used=result.get("xpath_used"),
                **page.response_metadata(),
            )
        return success_response(
            elements=page.items,
            xpath_used=result.get("xpath_used"),
            **page.response_metadata(),
        )
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error finding matrix elements")
        return error_response(str(e), transient=False)


async def set_matrix_element_property(
    property_name: str,
    value: PropertyValue,
    element_name: Optional[str] = None,
    element_type: Optional[str] = None,
    xpath: Optional[str] = None,
    view: str = "clusters",
    allow_multiple: bool = False,
) -> str:
    try:
        canonical_name, alias_used = resolve_bus_element_property_name(property_name)
        is_valid, type_error = validate_bus_element_property_value(
            canonical_name,
            value,
            scope="matrix",
        )
        if not is_valid:
            return error_response(
                type_error,
                transient=False,
                error_code="INVALID_VALUE_TYPE",
                recovery_hint=(
                    "The value type does not match the selected matrix element "
                    "property. Re-read the error message for the expected type "
                    "and example value."
                ),
            )

        conn = get_connection()
        result = await dispatch(
            matrix_com.set_matrix_element_property,
            conn,
            canonical_name,
            value,
            element_name,
            element_type,
            xpath,
            view,
            allow_multiple,
        )
        if result.get("error"):
            return error_response(result["detail"], transient=False)

        actual_name = result.get("property_name", canonical_name)
        if alias_used:
            message = (
                f"Property '{alias_used}' (resolved to '{actual_name}') set on "
                f"{result['set_count']} matrix element(s)"
            )
        else:
            message = f"Property '{actual_name}' set on {result['set_count']} matrix element(s)"
        return success_response(
            message=message,
            elements=result.get("elements", []),
            verified_count=result.get("verified_count", 0),
            mismatch_count=result.get("mismatch_count", 0),
            xpath_used=result.get("xpath_used"),
            relation=result.get("relation"),
        )
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error setting matrix element property")
        return error_response(str(e), transient=False)
