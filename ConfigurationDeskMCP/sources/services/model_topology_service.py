# -*- coding: utf-8 -*-
"""Model topology service."""

from __future__ import annotations

from typing import Optional

from configurationdesk_com_bridge import dispatch, get_connection
from configurationdesk_com_bridge.domains import model_topology_com
from configurationdesk_com_bridge.errors import BridgeError

from sources.models.envelope_builder import tool_error_result
from sources.services._observations import dispatch_observation
from sources.services._workflow_readiness import (
    require_model_ports_ready,
    require_model_ready,
)
from sources.tools._responses import error_response, success_response, unverified_response
from sources.utils.logger import get_logger

logger = get_logger(__name__)


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


async def create_application_process(
    name: Optional[str] = None,
    bus_config_names: Optional[list[str]] = None,
) -> str:
    try:
        conn = get_connection()
        result = await dispatch(
            model_topology_com.create_application_process,
            conn,
            name,
            bus_config_names,
            timeout_ms=120000,
        )
        if result.get("error"):
            return error_response(result["detail"], transient=False)
        if result.get("verified"):
            payload = dict(result)
            payload.pop("verified", None)
            process_name = payload.get("process_name") or "(default name)"
            default_task_set = payload.get("default_task_set")
            if default_task_set:
                msg = (
                    f"Application process '{process_name}' created with a default task "
                    f"({payload.get('default_task_property') or 'ProvideDefaultTask'} = True)."
                )
            else:
                msg = (
                    f"Application process '{process_name}' created, but the "
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
                "Verify a ProcessingUnitApplication exists (use `add_application_processing_unit` "
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
            message=f"All ports of model '{model_name}' added to the signal chain",
            verified=True,
            **result,
        )
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error adding model to signal chain")
        return error_response(str(e), transient=False)


async def add_model_port_to_signal_chain(model_name: str, port_name: str) -> str:
    try:
        conn = get_connection()
        ports = await require_model_ports_ready(conn, model_name)
        if port_name not in ports:
            return error_response(
                f"Model '{model_name}' does not expose a port named '{port_name}'.",
                transient=False,
                next_action="Call `list_model_ports` first and use one of the returned port names.",
            )
        result = await dispatch(
            model_topology_com.add_model_port_to_signal_chain, conn, model_name, port_name
        )
        return success_response(
            message=f"Port '{port_name}' of model '{model_name}' added to the signal chain",
            verified=True,
            **result,
        )
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error adding model port to signal chain")
        return error_response(str(e), transient=False)


async def list_model_ports(model_name: str) -> str:
    try:
        conn = get_connection()
        await require_model_ready(conn, model_name)
        ports = await dispatch_observation(model_topology_com.list_model_ports, conn, model_name)
        return success_response(model_name=model_name, ports=ports, count=len(ports))
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error listing model ports")
        return error_response(str(e), transient=False)
