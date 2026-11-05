# -*- coding: utf-8 -*-
"""Model topology service."""

from __future__ import annotations

import os
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
ApplicationProcessChooser = Callable[[list[str]], Awaitable[Optional[str]]]

SUPPORTED_MODEL_EXTENSIONS = (".slx", ".mdl", ".sic", ".bsc", ".fmu")
_ANALYZED_MODEL_EXTENSIONS = (".slx", ".mdl")
_ADD_MODELS_BASE_TIMEOUT_MS = 300_000
_ADD_MODELS_PER_MODEL_TIMEOUT_MS = 180_000


def analyze_on_add(path: str) -> bool:
    """Simulink models are analyzed when added; container files already define their interface."""
    return path.lower().endswith(_ANALYZED_MODEL_EXTENSIONS)


def _prepare_model_files(paths: list[str]) -> tuple[list[tuple[str, bool]], Optional[str]]:
    """Return ``[(absolute_path, analyze)]`` or an error response for invalid input."""
    if not paths:
        return [], error_response("No model file was given.", transient=False)
    models: list[tuple[str, bool]] = []
    seen: set[str] = set()
    unsupported: list[str] = []
    missing: list[str] = []
    for path in paths:
        abs_path = os.path.abspath(path)
        if abs_path.lower() in seen:
            continue
        seen.add(abs_path.lower())
        if not abs_path.lower().endswith(SUPPORTED_MODEL_EXTENSIONS):
            unsupported.append(path)
        elif not os.path.isfile(abs_path):
            missing.append(abs_path)
        else:
            models.append((abs_path, analyze_on_add(abs_path)))
    if unsupported:
        return [], error_response(
            f"Unsupported model file type: {', '.join(unsupported)}. "
            f"Supported: {', '.join(SUPPORTED_MODEL_EXTENSIONS)}.",
            transient=False,
        )
    if missing:
        return [], error_response(
            f"Model file not found: {', '.join(missing)}.",
            transient=False,
            next_action="Ask the user for the correct model file path, then call `add_model` again.",
        )
    return models, None


def _add_models_timeout_ms(count: int) -> int:
    return _ADD_MODELS_BASE_TIMEOUT_MS + _ADD_MODELS_PER_MODEL_TIMEOUT_MS * max(count - 1, 0)


def _match_name(names: list[str], wanted: str) -> Optional[str]:
    if wanted in names:
        return wanted
    return next((name for name in names if name.lower() == wanted.lower()), None)


def _added_models_response(
    result: dict,
    *,
    mode: str,
    requested: int,
    processing_unit_application: Optional[str] = None,
    workaround: bool = False,
) -> str:
    added = result.get("added", [])
    assignments = result.get("assignments", {})
    payload = {
        "application_process_mode": mode,
        "added": added,
        "assignments": assignments,
        "created_processes": result.get("created_processes", []),
        "all_models": result.get("all_models", []),
    }
    if processing_unit_application:
        payload["processing_unit_application"] = processing_unit_application
    if workaround:
        payload["multiple_processing_unit_applications_workaround"] = True
    for key in ("application_process", "optimized", "optimize_detail", "failed", "rename_detail"):
        if result.get(key) not in (None, "", []):
            payload[key] = result[key]

    if not added:
        failed = result.get("failed") or []
        detail = "; ".join(f"{item['path']}: {item['detail']}" for item in failed)
        return error_response(
            "No model was added." + (f" {detail}" if detail else ""),
            transient=False,
        )

    unassigned = [model for model in added if not assignments.get(model)] if mode != "none" else []
    issues: list[str] = []
    if len(added) < requested or result.get("failed"):
        issues.append(f"only {len(added)} of {requested} model(s) were added")
    if unassigned:
        issues.append(f"not assigned to an application process: {', '.join(unassigned)}")
    if mode == "new_shared":
        processes = {process for model in added for process in assignments.get(model, [])}
        if len(processes) > 1:
            issues.append(f"models ended up in several application processes: {sorted(processes)}")
    if result.get("rename_detail"):
        issues.append(result["rename_detail"])
    if result.get("optimize_detail"):
        issues.append(result["optimize_detail"])

    message = f"Added {len(added)} model(s): {', '.join(added)}."
    if issues:
        return unverified_response(
            message=message + " Issues: " + "; ".join(issues) + ".", **payload
        )
    return success_response(message=message, verified=True, **payload)


async def _resolve_processing_unit_application(
    conn,
    requested: Optional[str],
    choose: Optional[ProcessingUnitApplicationChooser],
) -> tuple[Optional[str], list[str], Optional[str]]:
    """Return ``(name, available_names, error)`` for the host processing unit application."""
    names = await _list_processing_unit_application_names(conn)
    if requested is not None:
        match = _match_name(names, requested)
        if match is None:
            return (
                None,
                names,
                error_response(
                    f"Processing unit application '{requested}' not found. "
                    f"Available: {', '.join(names) or '(none)'}.",
                    transient=False,
                ),
            )
        return match, names, None
    if len(names) <= 1:
        return (names[0] if names else None), names, None
    chosen = await choose(names) if choose is not None else None
    match = _match_name(names, chosen) if chosen else None
    if match is None:
        return (
            None,
            names,
            error_response(
                "The executable application contains several processing unit applications "
                f"({', '.join(names)}). The processing unit application for the new application "
                "process(es) was not selected.",
                transient=False,
                next_action=(
                    "Ask the user which processing unit application should host the application "
                    "process(es), then call `add_model` again with `processing_unit_application` set "
                    "to that name."
                ),
            ),
        )
    return match, names, None


async def _resolve_existing_application_process(
    conn,
    requested: Optional[str],
    choose: Optional[ApplicationProcessChooser],
) -> tuple[Optional[str], Optional[str]]:
    """Return ``(name, error)`` for the existing target application process."""
    names = list(await dispatch(model_topology_com.list_application_process_names, conn))
    if not names:
        return None, error_response(
            "The application contains no application process to add the models to.",
            transient=False,
            next_action=(
                "Call `add_model` with application_process_mode='new_shared' or 'per_model', or "
                "create one with `create_application_process` first."
            ),
        )
    if requested is not None:
        match = _match_name(names, requested)
        if match is None:
            return None, error_response(
                f"Application process '{requested}' not found. Available: {', '.join(names)}.",
                transient=False,
            )
        return match, None
    if len(names) == 1:
        return names[0], None
    chosen = await choose(names) if choose is not None else None
    match = _match_name(names, chosen) if chosen else None
    if match is None:
        return None, error_response(
            "The application contains several application processes "
            f"({', '.join(names)}). The target application process was not selected.",
            transient=False,
            next_action=(
                "Ask the user which application process should receive the models, then call "
                "`add_model` again with `application_process` set to that name."
            ),
        )
    return match, None


async def add_models(
    paths: list[str],
    application_process_mode: str = "per_model",
    application_process: Optional[str] = None,
    processing_unit_application: Optional[str] = None,
    optimize_configuration: bool = True,
    choose_application_process: Optional[ApplicationProcessChooser] = None,
    choose_processing_unit_application: Optional[ProcessingUnitApplicationChooser] = None,
) -> str:
    """Add model files and assign them to application processes according to the mode.

    Modes: ``per_model`` (one preconfigured application process per model),
    ``none`` (no application process), ``existing`` (add to an existing
    application process) and ``new_shared`` (one new, optimized application
    process for all models).

    ConfigurationDesk only creates application processes while adding models
    when at most one processing unit application exists. With several, the
    processing unit application is selected and the application processes are
    created there in separate steps.
    """
    models, error = _prepare_model_files(paths)
    if error is not None:
        return error
    mode = application_process_mode
    timeout_ms = _add_models_timeout_ms(len(models))
    try:
        conn = get_connection()

        if mode == "none":
            result = await dispatch(
                model_topology_com.add_models,
                conn,
                models,
                model_topology_com.AP_NONE,
                None,
                timeout_ms=timeout_ms,
            )
            return _added_models_response(result, mode=mode, requested=len(models))

        if mode == "existing":
            target, error = await _resolve_existing_application_process(
                conn, application_process, choose_application_process
            )
            if error is not None:
                return error
            result = await dispatch(
                model_topology_com.add_models_to_application_process,
                conn,
                models,
                target,
                optimize_configuration,
                timeout_ms=timeout_ms,
            )
            return _added_models_response(result, mode=mode, requested=len(models))

        if mode not in ("per_model", "new_shared"):
            return error_response(f"Unknown application_process_mode '{mode}'.", transient=False)

        pua, pua_names, error = await _resolve_processing_unit_application(
            conn, processing_unit_application, choose_processing_unit_application
        )
        if error is not None:
            return error

        if len(pua_names) <= 1:
            native_mode = (
                model_topology_com.AP_ONE_FOR_EACH
                if mode == "per_model"
                else model_topology_com.AP_ONE_FOR_ALL
            )
            result = await dispatch(
                model_topology_com.add_models,
                conn,
                models,
                native_mode,
                application_process if mode == "new_shared" else None,
                timeout_ms=timeout_ms,
            )
            return _added_models_response(
                result, mode=mode, requested=len(models), processing_unit_application=pua
            )

        if mode == "per_model":
            result = await dispatch(
                model_topology_com.add_models,
                conn,
                models,
                model_topology_com.AP_NONE,
                None,
                timeout_ms=timeout_ms,
            )
            if result.get("added"):
                created = await dispatch(
                    model_topology_com.create_preconfigured_application_processes,
                    conn,
                    result["added"],
                    pua,
                    timeout_ms=timeout_ms,
                )
                if created.get("error"):
                    result["failed"] = [
                        {"path": "(application processes)", "detail": created["detail"]}
                    ]
                else:
                    result["created_processes"] = created.get("created_processes", [])
                    result["assignments"] = created.get("assignments", {})
            return _added_models_response(
                result,
                mode=mode,
                requested=len(models),
                processing_unit_application=pua,
                workaround=True,
            )

        process = await dispatch(
            model_topology_com.create_application_process,
            conn,
            application_process,
            [],
            False,
            pua,
            timeout_ms=120_000,
        )
        if process.get("error") or not process.get("verified"):
            return error_response(
                "Could not create the application process for the models: "
                f"{process.get('detail') or 'no new application process became observable'}",
                transient=False,
            )
        result = await dispatch(
            model_topology_com.add_models_to_application_process,
            conn,
            models,
            process["process_name"],
            True,
            timeout_ms=timeout_ms,
        )
        result["created_processes"] = process.get("created_processes", [])
        return _added_models_response(
            result,
            mode=mode,
            requested=len(models),
            processing_unit_application=pua,
            workaround=True,
        )
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error adding models")
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
