# -*- coding: utf-8 -*-
"""Communication matrix service."""

from __future__ import annotations

import json
from typing import Any, Optional

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


_REPLACE_ERROR_GUIDANCE: dict[str, tuple[str, str]] = {
    "bus_config_not_found": (
        "BUS_CONFIG_NOT_FOUND",
        "Call `list_bus_configurations` and retry with an exact bus configuration name.",
    ),
    "no_assigned_matrix": (
        "MATRIX_NOT_ASSIGNED",
        "Assign matrix elements with `assign_ecu_to_bus_config` or "
        "`assign_matrix_to_bus_config` instead of replacing an assignment.",
    ),
    "ambiguous_assigned_matrix": (
        "AMBIGUOUS_MATRIX_ASSIGNMENT",
        "Retry with `assigned_matrix_name` set to one of the listed matrix nodes.",
    ),
    "assigned_matrix_not_found": (
        "MATRIX_NOT_ASSIGNED",
        "Retry with `assigned_matrix_name` set to one of the listed matrix nodes.",
    ),
    "new_matrix_not_found": (
        "MATRIX_NOT_FOUND",
        "Load the new matrix with `add_communication_matrix` first, or retry with "
        "one of the listed loaded matrices from `list_matrices`.",
    ),
    "ambiguous_loaded_matrix": (
        "AMBIGUOUS_MATRIX_NAME",
        "Use distinct filenames for matrix versions before importing them, and select a "
        "unique loaded name from `list_matrices`. Inspect existing assignments before "
        "removing or reloading duplicates. No replacement was performed.",
    ),
    "ambiguous_assigned_source": (
        "AMBIGUOUS_MATRIX_ASSIGNMENT",
        "Give the intended assigned matrix node a unique name in ConfigurationDesk, then retry "
        "with that exact assigned_matrix_name. No replacement was performed.",
    ),
    "matrix_source_unavailable": (
        "MATRIX_SOURCE_UNAVAILABLE",
        "Inspect the matrix source properties in ConfigurationDesk before retrying. "
        "No replacement was performed.",
    ),
    "replacing_conditions_unavailable": (
        "REPLACING_CONDITIONS_UNAVAILABLE",
        "Inspect the 'Use additional replacing conditions' option in ConfigurationDesk. "
        "No setting or assignment was changed; do not retry until its value can be read.",
    ),
    "new_matrix_already_assigned": (
        "MATRIX_ALREADY_ASSIGNED",
        "The requested source is already assigned to this bus configuration. Select an "
        "unassigned matrix version. No setting or assignment was changed.",
    ),
}


def _with_names(detail: str, label: str, names: Optional[list[str]]) -> str:
    if names is None:
        return detail
    return f"{detail}. {label}: {names}" if names else f"{detail}. {label}: none"


def _replacement_verified(result: dict) -> bool:
    expected = result.get("expected_source") or {}
    before = result.get("assigned_sources_before") or []
    after = result.get("assigned_sources_after") or []
    required = ("File name", "File path", "Content hash")
    return (
        all(isinstance(expected.get(name), str) and expected[name].strip() for name in required)
        and bool(after)
        and len(after) == len(before)
        and all(source == expected for source in after)
    )


def _xpath_literal(value: str) -> str:
    if '"' not in value:
        return f'"{value}"'
    if "'" not in value:
        return f"'{value}'"
    parts = value.split('"')
    return "concat(" + ", '\"', ".join(f'"{part}"' for part in parts) + ")"


def _as_bool(value: Any) -> Optional[bool]:
    if isinstance(value, (list, tuple)) and len(value) == 1:
        value = value[0]
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    return None


def _execute_matrix_replacement(
    connection,
    bus_config_name: str,
    new_matrix_name: str,
    assigned_matrix_name: Optional[str] = None,
    use_additional_replacing_conditions: Optional[bool] = None,
) -> dict[str, Any]:
    """Resolve, replace, and restore options within one uninterrupted STA task."""
    assigned_xpath = (
        f"/BusConfiguration[@Name={_xpath_literal(bus_config_name)}]//BusCommunicationMatrix"
    )
    state = matrix_com.read_matrix_replacement_state(connection, assigned_xpath)
    if bus_config_name not in state["bus_configurations"]:
        return {
            "error": True,
            "error_kind": "bus_config_not_found",
            "detail": f"Bus configuration '{bus_config_name}' not found",
            "bus_configurations": state["bus_configurations"],
        }
    assigned = state["assigned"]
    assigned_before = list(dict.fromkeys(node["name"] for node in assigned))
    if not assigned_before:
        return {
            "error": True,
            "error_kind": "no_assigned_matrix",
            "detail": f"Bus configuration '{bus_config_name}' has no assigned communication matrix",
            "assigned_matrices": [],
        }
    if assigned_matrix_name is None:
        if len(assigned_before) != 1:
            return {
                "error": True,
                "error_kind": "ambiguous_assigned_matrix",
                "detail": (
                    f"Bus configuration '{bus_config_name}' has {len(assigned_before)} assigned "
                    "communication matrices; specify assigned_matrix_name"
                ),
                "assigned_matrices": assigned_before,
            }
        assigned_matrix_name = assigned_before[0]
    matching_assigned = [
        index for index, node in enumerate(assigned) if node["name"] == assigned_matrix_name
    ]
    if not matching_assigned:
        return {
            "error": True,
            "error_kind": "assigned_matrix_not_found",
            "detail": (
                f"Communication matrix node '{assigned_matrix_name}' is not assigned to "
                f"bus configuration '{bus_config_name}'"
            ),
            "assigned_matrices": assigned_before,
        }
    loaded = state["loaded"]
    loaded_names = [node["name"] for node in loaded]
    matching_loaded = [
        index for index, node in enumerate(loaded) if node["name"] == new_matrix_name
    ]
    if not matching_loaded:
        return {
            "error": True,
            "error_kind": "new_matrix_not_found",
            "detail": f"Communication matrix '{new_matrix_name}' is not loaded in the application",
            "loaded_matrices": loaded_names,
        }
    if len(matching_loaded) != 1:
        return {
            "error": True,
            "error_kind": "ambiguous_loaded_matrix",
            "detail": (
                f"Communication matrix name '{new_matrix_name}' matches "
                f"{len(matching_loaded)} loaded matrices; use a uniquely named matrix version"
            ),
            "loaded_matrices": loaded_names,
        }
    expected_source = loaded[matching_loaded[0]]["source"]
    sources_before = [assigned[index]["source"] for index in matching_assigned]
    if any(not all(source.values()) for source in [expected_source, *sources_before]):
        return {
            "error": True,
            "error_kind": "matrix_source_unavailable",
            "detail": "Cannot read the file name, file path, and content hash of the matrix sources",
        }
    if any(source != sources_before[0] for source in sources_before):
        return {
            "error": True,
            "error_kind": "ambiguous_assigned_source",
            "detail": (
                f"Assigned matrix name '{assigned_matrix_name}' identifies different source files; "
                "give the intended assigned matrix a unique name"
            ),
            "assigned_matrices": assigned_before,
        }
    if any(node["source"] == expected_source for node in assigned):
        return {
            "error": True,
            "error_kind": "new_matrix_already_assigned",
            "detail": f"Communication matrix '{new_matrix_name}' is already assigned to this bus configuration",
        }

    conditions: dict[str, Any] = {
        "requested": use_additional_replacing_conditions,
        "previous": None,
        "restored": None,
    }
    result: dict[str, Any] = {
        "bus_config_name": bus_config_name,
        "replaced_matrix_node": assigned_matrix_name,
        "new_matrix": new_matrix_name,
        "assigned_matrices_before": assigned_before,
        "assigned_matrices_after": assigned_before,
        "expected_source": expected_source,
        "assigned_sources_before": sources_before,
        "assigned_sources_after": [],
        "deprecated_nodes": [],
        "additional_replacing_conditions": conditions,
    }
    if use_additional_replacing_conditions is not None:
        try:
            previous = _as_bool(matrix_com.get_additional_replacing_conditions(connection))
        except Exception as exc:
            previous = None
            conditions["read_error"] = str(exc)
        if previous is None:
            return {
                **result,
                "error": True,
                "error_kind": "replacing_conditions_unavailable",
                "detail": "Cannot read the original additional replacing conditions setting",
            }
        conditions["previous"] = previous

    changed_option = (
        use_additional_replacing_conditions is not None
        and conditions["previous"] != use_additional_replacing_conditions
    )
    try:
        if changed_option:
            result["override_failed"] = True
            matrix_com.set_additional_replacing_conditions(
                connection, bool(use_additional_replacing_conditions)
            )
            observed = _as_bool(matrix_com.get_additional_replacing_conditions(connection))
            if observed is not use_additional_replacing_conditions:
                raise RuntimeError("Read-back did not confirm the requested replacing conditions")
            result["override_failed"] = False
        matrix_com.replace_communication_matrix_assignment(
            connection, assigned_xpath, matching_assigned[0], matching_loaded[0]
        )
    except Exception as exc:
        result["operation_error"] = exc
    finally:
        if use_additional_replacing_conditions is not None:
            try:
                if changed_option:
                    matrix_com.set_additional_replacing_conditions(
                        connection, conditions["previous"]
                    )
                observed = _as_bool(matrix_com.get_additional_replacing_conditions(connection))
                if observed is not conditions["previous"]:
                    raise RuntimeError(
                        "Read-back did not confirm the original replacing conditions"
                    )
                conditions["restored"] = True
            except Exception as exc:
                conditions["restored"] = False
                conditions["restoration_error"] = str(exc)
    try:
        after = matrix_com.read_matrix_replacement_state(connection, assigned_xpath)["assigned"]
        assigned_after = list(dict.fromkeys(node["name"] for node in after))
        result["assigned_matrices_after"] = assigned_after
        result["assigned_sources_after"] = [
            node["source"] for node in after if node["name"] == assigned_matrix_name
        ]
        result["deprecated_nodes"] = [
            name
            for name in assigned_after
            if name not in assigned_before
            and name.startswith(f"{assigned_matrix_name} (deprecated")
        ]
    except Exception as exc:
        result.setdefault("operation_error", exc)
    return result


def _replacement_error_result(payload: str, result: dict) -> str:
    envelope = json.loads(payload)
    if "additional_replacing_conditions" in result:
        envelope["additional_replacing_conditions"] = result["additional_replacing_conditions"]
    envelope["replacement_verified"] = _replacement_verified(result)
    if result.get("operation_error") is not None:
        envelope["replacement_error"] = str(result["operation_error"])
    return json.dumps(envelope, indent=2, default=str)


async def replace_communication_matrix_assignment(
    bus_config_name: str,
    new_matrix_name: str,
    assigned_matrix_name: Optional[str] = None,
    use_additional_replacing_conditions: Optional[bool] = None,
) -> str:
    try:
        conn = get_connection()
        result = await dispatch(
            _execute_matrix_replacement,
            conn,
            bus_config_name,
            new_matrix_name,
            assigned_matrix_name,
            use_additional_replacing_conditions,
        )
        if result.get("error"):
            error_code, next_action = _REPLACE_ERROR_GUIDANCE.get(
                result.get("error_kind", ""),
                ("BRIDGE_UNKNOWN", ""),
            )
            detail = result["detail"]
            detail = _with_names(detail, "Bus configurations", result.get("bus_configurations"))
            detail = _with_names(detail, "Assigned matrix nodes", result.get("assigned_matrices"))
            detail = _with_names(detail, "Loaded matrices", result.get("loaded_matrices"))
            return _replacement_error_result(
                error_response(
                    detail, transient=False, error_code=error_code, next_action=next_action
                ),
                result,
            )

        conditions = result.get("additional_replacing_conditions") or {}
        if conditions.get("requested") is not None and conditions.get("restored") is False:
            primary_error = result.get("operation_error")
            detail = (
                f"Replacement failed: {primary_error}. "
                if primary_error is not None
                else "Replacement source verified, but "
                if _replacement_verified(result)
                else "Replacement could not be verified, and "
            )
            return _replacement_error_result(
                error_response(
                    detail + "the original additional replacing conditions setting could not be "
                    f"restored: {conditions.get('restoration_error', 'restoration unconfirmed')}",
                    error_code="REPLACING_CONDITIONS_RESTORE_FAILED",
                    next_action=(
                        "Restore 'Use additional replacing conditions' in ConfigurationDesk Options "
                        f"to {conditions.get('previous')} and inspect the bus configuration. "
                        "Do not retry replacement or continue the workflow before restoring it."
                    ),
                ),
                result,
            )
        operation_error = result.get("operation_error")
        if operation_error is not None:
            if result.get("override_failed"):
                payload = error_response(
                    f"The requested additional replacing conditions could not be set and confirmed: "
                    f"{operation_error}. No replacement was performed.",
                    error_code="REPLACING_CONDITIONS_SET_FAILED",
                    next_action=(
                        "Inspect the 'Use additional replacing conditions' option in ConfigurationDesk "
                        "and the reported restoration status before retrying. "
                        "Do not continue the workflow with an unconfirmed option override."
                    ),
                )
            else:
                payload = (
                    tool_error_result(operation_error)
                    if isinstance(operation_error, BridgeError)
                    else error_response(str(operation_error), transient=False)
                )
            return _replacement_error_result(payload, result)
        if not _replacement_verified(result):
            return _replacement_error_result(
                error_response(
                    f"Replacement issued, but not all instances of matrix node "
                    f"'{result['replaced_matrix_node']}' in bus configuration '{bus_config_name}' "
                    f"could be confirmed to use '{new_matrix_name}' by file name, file path, and "
                    f"content hash. Assigned matrix nodes now: {result.get('assigned_matrices_after')}",
                    transient=False,
                    error_code="VERIFICATION_FAILED",
                    next_action=(
                        "Call `find_bus_config_elements` with xpath='//BusCommunicationMatrix' "
                        "and `check_conflicts` to inspect the bus configuration."
                    ),
                ),
                result,
            )

        warnings: list[str] = []
        deprecated_nodes = result.get("deprecated_nodes", [])
        if deprecated_nodes:
            warnings.append(
                "Some assigned elements could not be identified in the new matrix and were "
                f"kept unchanged in deprecated node(s): {deprecated_nodes}. Review them and "
                "remove them with `remove_bus_config_elements` if they are no longer needed."
            )
        return success_response(
            message=(
                f"Matrix node '{result['replaced_matrix_node']}' in bus configuration "
                f"'{bus_config_name}' now uses communication matrix '{new_matrix_name}'"
            ),
            verified=True,
            bus_config_name=bus_config_name,
            replaced_matrix_node=result["replaced_matrix_node"],
            new_matrix=new_matrix_name,
            deprecated_nodes=deprecated_nodes,
            assigned_matrices=result.get("assigned_matrices_after", []),
            additional_replacing_conditions=conditions,
            warnings=warnings,
            next_action=(
                "Call `check_conflicts` to review conflicts caused by matrix differences, "
                "then update model port blocks mapped to this bus configuration if the "
                "signal interface changed."
            ),
        )
    except BridgeError as exc:
        return _replacement_error_result(
            tool_error_result(exc),
            {
                "additional_replacing_conditions": {
                    "requested": use_additional_replacing_conditions,
                    "previous": None,
                    "restored": None,
                },
            },
        )
    except Exception as e:
        logger.exception("Error replacing communication matrix assignment")
        return _replacement_error_result(
            error_response(str(e), transient=False),
            {
                "additional_replacing_conditions": {
                    "requested": use_additional_replacing_conditions,
                    "previous": None,
                    "restored": None,
                },
            },
        )


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
