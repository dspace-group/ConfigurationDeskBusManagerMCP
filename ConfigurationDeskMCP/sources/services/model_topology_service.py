# -*- coding: utf-8 -*-
"""Model topology service."""

from __future__ import annotations

from typing import Awaitable, Callable, Optional

from configurationdesk_com_bridge import dispatch, get_connection
from configurationdesk_com_bridge.domains import app_management_com, model_topology_com
from configurationdesk_com_bridge.errors import BridgeError

from sources.models.envelope_builder import tool_error_result
from sources.services._model_port_blocks import ambiguous_model_port_block_response
from sources.services._observations import dispatch_observation
from sources.services._workflow_readiness import (
    require_model_port_blocks_ready,
    require_model_ready,
)
from sources.tools._responses import error_response, success_response, unverified_response
from sources.utils.logger import get_logger

logger = get_logger(__name__)

ProcessingUnitApplicationChooser = Callable[[list[str]], Awaitable[Optional[str]]]


async def add_model(path: str, analyze: bool = True, create_preconfigured: bool = True) -> str:
    try:
        conn = get_connection()
        result = await dispatch(
            model_topology_com.add_model,
            conn,
            path,
            analyze,
            create_preconfigured,
            timeout_ms=300_000,
        )
        if result.get("verified"):
            return success_response(
                message=f"Model added from '{path}'",
                verified=True,
                added=result.get("added", []),
                all_models=result.get("all_models", []),
            )
        return error_response(
            f"Model add command issued but no new models detected after adding '{path}'",
            transient=False,
        )
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error adding model")
        return error_response(str(e), transient=False)


async def replace_model(path: str, model_name: Optional[str] = None, analyze: bool = True) -> str:
    try:
        conn = get_connection()
        if model_name:
            await require_model_ready(conn, model_name)
        result = await dispatch(model_topology_com.replace_model, conn, path, model_name, analyze)
        return success_response(message=f"Model replaced with '{path}'", verified=True, **result)
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error replacing model")
        return error_response(str(e), transient=False)


async def remove_model(name: str) -> str:
    try:
        conn = get_connection()
        models = await require_model_ready(conn)
        resolved_name = next(
            (
                model_name
                for model_name in models
                if model_name == name
                or model_name.lower() == name.lower()
                or model_name.lower().startswith(name.lower())
                or name.lower().startswith(model_name.lower())
            ),
            None,
        )
        if resolved_name is None:
            return error_response(
                f"Model '{name}' is not ready in the active application.",
                transient=False,
                next_action="Call `list_models` and use one of the returned model names for removal.",
            )
        result = await dispatch(model_topology_com.remove_model, conn, resolved_name)
        if result.get("verified"):
            return success_response(message=f"Model '{resolved_name}' removed", verified=True)
        return error_response(result.get("detail", "Removal failed"), transient=False)
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error removing model")
        return error_response(str(e), transient=False)


async def analyze_models() -> str:
    try:
        conn = get_connection()
        await require_model_ready(conn)
        await dispatch(model_topology_com.analyze_models, conn)
        return unverified_response(message="Model analysis command issued")
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error analyzing models")
        return error_response(str(e), transient=False)


async def _list_processing_unit_application_names(conn) -> list[str]:
    return list(await dispatch(model_topology_com.list_processing_unit_application_names, conn))


def _processing_unit_application_choice_required(names: list[str]) -> str:
    return error_response(
        "The executable application contains several processing unit applications "
        f"({', '.join(names)}). The target processing unit application for the new "
        "application process was not selected.",
        transient=False,
        next_action=(
            "Ask the user which processing unit application should host the application "
            "process, then call `create_application_process` again with "
            "`processing_unit_application` set to that name."
        ),
    )


async def select_processing_unit_application(
    choose: Optional[ProcessingUnitApplicationChooser] = None,
) -> tuple[Optional[str], Optional[str]]:
    """Select the processing unit application that hosts a new application process.

    Returns ``(name, error)``:

    * no processing unit application → ``(None, None)``; one is created by
      :func:`create_application_process`.
    * exactly one → ``(name, None)``.
    * several → *choose* is asked for the name; ``(None, error)`` when no valid
      choice is made.
    """
    try:
        conn = get_connection()
        names = await _list_processing_unit_application_names(conn)
    except BridgeError as exc:
        return None, tool_error_result(exc)
    except Exception as e:
        logger.exception("Error listing processing unit applications")
        return None, error_response(str(e), transient=False)

    if not names:
        return None, None
    if len(names) == 1:
        return names[0], None

    chosen = await choose(names) if choose is not None else None
    if chosen in names:
        return chosen, None
    if chosen:
        match = next((n for n in names if n.lower() == chosen.lower()), None)
        if match is not None:
            return match, None
    return None, _processing_unit_application_choice_required(names)


async def create_application_process(
    name: Optional[str] = None,
    bus_config_names: Optional[list[str]] = None,
    provide_default_task: bool = True,
    processing_unit_application: Optional[str] = None,
) -> str:
    """Create an application process on a processing unit application.

    Without *processing_unit_application*: a processing unit application is
    created when none exists, the only one is used when exactly one exists, and
    an error asking for a selection is returned when several exist.
    """
    try:
        conn = get_connection()
        pua_created = False
        if processing_unit_application is None:
            names = await _list_processing_unit_application_names(conn)
            if not names:
                created = await dispatch(app_management_com.add_processing_unit_application, conn)
                if not created.get("processing_unit_application_created"):
                    return error_response(
                        "No processing unit application exists and none could be created: "
                        f"{created.get('processing_unit_application_detail', '')}",
                        transient=False,
                        next_action=(
                            "Add a processing unit application in ConfigurationDesk (Processing "
                            "Resource Assignment table → New → Processing Unit Application), then retry."
                        ),
                    )
                pua_created = True
                names = await _list_processing_unit_application_names(conn)
            if len(names) > 1:
                return _processing_unit_application_choice_required(names)
            if names:
                processing_unit_application = names[0]

        result = await dispatch(
            model_topology_com.create_application_process,
            conn,
            name,
            bus_config_names,
            provide_default_task,
            processing_unit_application,
            timeout_ms=120000,
        )
        if result.get("error"):
            return error_response(result["detail"], transient=False)
        if result.get("verified"):
            payload = dict(result)
            payload.pop("verified", None)
            payload["processing_unit_application_created"] = pua_created
            process_name = payload.get("process_name") or "(default name)"
            pua_name = payload.get("processing_unit_application") or processing_unit_application
            location = f" on processing unit application '{pua_name}'" if pua_name else ""
            if pua_created:
                location += " (created because none existed)"
            default_task_set = payload.get("default_task_set")
            if not provide_default_task:
                msg = (
                    f"Application process '{process_name}' created{location} without a default "
                    "task ('Provide default task' left disabled). Assign a model implementation, "
                    "then start the 'Optimize Configuration' command on the application process "
                    "before building."
                )
            elif default_task_set:
                msg = (
                    f"Application process '{process_name}' created{location} with a default task "
                    f"({payload.get('default_task_property') or 'ProvideDefaultTask'} = True)."
                )
            else:
                msg = (
                    f"Application process '{process_name}' created{location}, but the "
                    "'Provide default task' property could not be set automatically. "
                    "Open the application process properties in ConfigurationDesk and "
                    "enable 'Provide default task' manually."
                )
            return success_response(message=msg, verified=True, **payload)
        payload = dict(result)
        payload.pop("verified", None)
        return error_response(
            "No new application process became observable after the creation call.",
            transient=False,
            next_action=(
                "Verify a ProcessingUnitApplication exists (use `add_processing_unit_application` "
                "for VEOS workflows or register a hardware platform), then retry."
            ),
        )
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error creating application process")
        return error_response(str(e), transient=False)


async def list_models() -> str:
    try:
        conn = get_connection()
        models = await dispatch_observation(model_topology_com.list_models, conn)
        return success_response(models=models)
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error listing models")
        return error_response(str(e), transient=False)


async def add_model_to_signal_chain(model_name: str) -> str:
    try:
        conn = get_connection()
        await require_model_ready(conn, model_name)
        result = await dispatch(model_topology_com.add_model_to_signal_chain, conn, model_name)
        return success_response(
            message=f"All model port blocks of model '{model_name}' added to the signal chain",
            verified=True,
            **result,
        )
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error adding model to signal chain")
        return error_response(str(e), transient=False)


async def add_model_port_block_to_signal_chain(model_name: str, port_block_name: str) -> str:
    try:
        conn = get_connection()
        await require_model_port_blocks_ready(conn, model_name)
        result = await dispatch(
            model_topology_com.add_model_port_block_to_signal_chain,
            conn,
            model_name,
            port_block_name,
        )
        if result.get("error"):
            return _port_block_error_response(result)
        path = result.get("port_block_path") or port_block_name
        return success_response(
            message=f"Model port block '{path}' of model '{model_name}' added to the signal chain",
            verified=True,
            **result,
        )
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error adding model port block to signal chain")
        return error_response(str(e), transient=False)


async def list_model_port_blocks(model_name: str) -> str:
    try:
        conn = get_connection()
        await require_model_ready(conn, model_name)
        blocks = await dispatch_observation(
            model_topology_com.list_model_port_blocks, conn, model_name
        )
        ambiguous: dict[str, list[str]] = {}
        for block in blocks:
            if block["identifier"] != block["name"]:
                ambiguous.setdefault(block["name"], []).append(block["path"])
        payload: dict = {
            "model_name": model_name,
            "port_blocks": [block["identifier"] for block in blocks],
            "port_block_paths": [block["path"] for block in blocks],
            "count": len(blocks),
        }
        if ambiguous:
            payload["ambiguous_names"] = ambiguous
            payload["note"] = (
                "Some model port block names occur at several hierarchy levels. If the user "
                "refers to one of these by name only, ask the user which path they mean "
                "before using it in another tool."
            )
        return success_response(**payload)
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error listing model port blocks")
        return error_response(str(e), transient=False)


async def list_model_ports(model_name: str, port_block_name: Optional[str] = None) -> str:
    try:
        conn = get_connection()
        await require_model_port_blocks_ready(conn, model_name)
        result = await dispatch_observation(
            model_topology_com.list_model_ports, conn, model_name, port_block_name
        )
        if result.get("error"):
            return _port_block_error_response(result)
        return success_response(**result)
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error listing model ports")
        return error_response(str(e), transient=False)


def _port_block_error_response(result: dict) -> str:
    if result.get("reason") == "ambiguous_model_port_block_hierarchy":
        return ambiguous_model_port_block_response(result["detail"], result.get("candidates", []))
    return error_response(
        result["detail"],
        transient=False,
        next_action=(
            "Call `list_model_port_blocks` first and use one of the returned names. "
            f"Available model port blocks: {result.get('available_port_blocks', [])}."
        ),
    )
