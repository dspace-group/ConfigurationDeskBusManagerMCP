# -*- coding: utf-8 -*-
"""Model topology tools for ConfigurationDesk MCP Server."""

from typing import Annotated

from pydantic import Field

from sources.models.model_topology_inputs import (
    AddModelInput,
    AddModelPortToSignalChainInput,
    AddModelToSignalChainInput,
    ListModelPortsInput,
    RemoveModelInput,
    ReplaceModelInput,
)
from sources.server.app import mcp
from sources.server.preconditions import with_preconditions
from sources.services import model_topology_service as svc


@mcp.tool(
    name="add_model",
    description=(
        "Add a behavior model file to the project's model topology. "
        "SUPPORTED FORMATS: .slx/.mdl (Simulink), .sic (pre-compiled SIC), .bsc (Bus Simulation Container). "
        "For .sic/.bsc files, analysis is skipped since ports are already defined. "
        "For Simulink models, set analyze=true (default) to detect model ports. "
        "WORKFLOW: add_model → analyze_models → create_application_process → "
        "auto_connect_matching_io_function_blocks_to_model_ports. "
        "Models provide the simulation behavior (plant model) that processes bus signals."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "application")
async def add_model(input: AddModelInput) -> str:
    return await svc.add_model(input.path, input.analyze, input.create_preconfigured)


@mcp.tool(
    name="replace_model",
    description=(
        "Replace an existing model with a new model file. "
        "Provide the path to the new model file and optionally the name of the model to replace."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "application", "model")
async def replace_model(input: ReplaceModelInput) -> str:
    return await svc.replace_model(input.path, input.model_name, input.analyze)


@mcp.tool(
    name="remove_model",
    description="Remove a model from the project",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "application", "model")
async def remove_model(input: RemoveModelInput) -> str:
    return await svc.remove_model(input.name)


@mcp.tool(
    name="analyze_models",
    description=(
        "Analyze all Simulink models in the project to detect their input/output ports and interfaces. "
        "Creates model port blocks in the signal chain that can be connected to bus function ports. "
        "Call after add_model and before auto_connect_matching_io_function_blocks_to_model_ports. "
        "Not needed for .sic/.bsc files (already analyzed). May take time for large models."
    ),
    annotations={
        # Not read-only: analysis creates model port blocks in the signal chain.
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "application", "model")
async def analyze_models() -> str:
    return await svc.analyze_models()


@mcp.tool(
    name="create_application_process",
    description=(
        "Create an application process that provides a default periodic task — the automation "
        "equivalent of the UI command 'New → Application Process (Providing Default Task)'. "
        "DECISION RULE: pick this tool when the user asks to create an application process and does "
        "NOT mention a specific behavior model. For the model-driven case, use "
        "`create_preconfigured_application_process` instead. "
        "WHAT IT DOES: on the active executable application's ProcessingUnitApplication it (1) "
        "creates an ApplicationProcess (optionally renamed via `name`) and (2) sets its "
        "'Provide default task' property to True so ConfigurationDesk auto-creates the periodic "
        "default task with a resolved runnable function — exactly like the UI command. "
        "BUS CONFIG ASSIGNMENT (default = ALL): the new application process is automatically "
        "assigned to every existing bus configuration (sets 'ManuallyAssignedApplicationProcess'). "
        "Pass `bus_config_names` to scope the assignment to specific configurations, or pass an "
        "empty list `[]` to skip assignment entirely. "
        "PRECONDITION: a ProcessingUnitApplication must exist (register a hardware platform or call "
        "`add_processing_unit_application` for VEOS workflows)."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "application")
async def create_application_process(
    name: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "Optional name for the new application process (e.g. 'Restbus_ApplicationProcess'). "
                "Omit to keep the ConfigurationDesk default name."
            ),
        ),
    ] = None,
    bus_config_names: Annotated[
        list[str] | None,
        Field(
            default=None,
            description=(
                "Bus configurations the new application process should be assigned to. "
                "Default (omit / null) = assign to ALL existing bus configurations. "
                "Provide a list (e.g. ['CAN_BodyBus']) to scope the assignment, or pass an "
                "empty list `[]` to skip assignment entirely."
            ),
        ),
    ] = None,
) -> str:
    return await svc.create_application_process(name, bus_config_names)


@mcp.tool(
    name="list_models",
    description=(
        "List all models in the project with their names and file paths. "
        "Shows the model topology including which models are loaded and their analysis state."
    ),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "application", "model")
async def list_models() -> str:
    return await svc.list_models()


@mcp.tool(
    name="add_model_to_signal_chain",
    description=(
        "[SIGNAL CHAIN — BULK] DECISION RULE: pick this tool when the user asks to add a MODEL "
        "(not a specific port) to the signal chain — i.e. NO port name is mentioned. If a port "
        "name is given, use add_model_port_to_signal_chain instead. "
        "TRIGGER PHRASES: 'add model <name> to signal chain', 'add all ports of <model> to signal "
        "chain', 'expose model <name> in signal chain', 'enable all model port blocks of <model>'. "
        "WHAT IT DOES: sets IsInApplication=True on EVERY model port block belonging to the named "
        "model, exposing all of them in the logical signal chain so they can later be wired to "
        "function blocks (e.g. via auto_connect_matching_io_function_blocks_to_model_ports). A model port block is "
        "the graphical representation of the ConfigurationDesk model interface in the signal chain. "
        "INPUT: model_name only — do NOT pass a port name. "
        "DOES NOT: add behavior models (use add_model), create connections "
        "(use auto_connect_matching_io_function_blocks_to_model_ports), or remove ports from the chain. "
        "PRECONDITION: the model must already be added (call add_model / analyze_models first)."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "application", "model")
async def add_model_to_signal_chain(input: AddModelToSignalChainInput) -> str:
    return await svc.add_model_to_signal_chain(input.model_name)


@mcp.tool(
    name="add_model_port_to_signal_chain",
    description=(
        "[SIGNAL CHAIN — SELECTIVE] DECISION RULE: pick this tool whenever the user names a SPECIFIC "
        "port / model port block (e.g. 'Sine_t', 'Throttle_In') alongside its model. If no port "
        "name is given, use add_model_to_signal_chain (BULK) instead. "
        "TRIGGER PHRASES: 'add model port block <port> of model <model> to signal chain', "
        "'add port <port> of <model> to signal chain', 'add <port> from <model> to the signal chain', "
        "'enable model port <port> of <model>'. "
        "WHAT IT DOES: sets IsInApplication=True on the SINGLE named model port block only; all "
        "other model port blocks of the model are unaffected. A model port block is the graphical "
        "representation of one model port (data port block, runnable function block, configuration "
        "port block, etc.) in the signal chain. "
        "INPUT: model_name AND port_name — if the exact port_name is unknown, call list_model_ports "
        "first to discover the valid identifiers. "
        "DOES NOT: add behavior models (use add_model), create connections "
        "(use auto_connect_matching_io_function_blocks_to_model_ports), or affect other ports of the same model. "
        "PRECONDITION: the model must already be added (call add_model / analyze_models first)."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "application", "model")
async def add_model_port_to_signal_chain(input: AddModelPortToSignalChainInput) -> str:
    return await svc.add_model_port_to_signal_chain(input.model_name, input.port_name)


@mcp.tool(
    name="list_model_ports",
    description=(
        "[SIGNAL CHAIN — DISCOVERY] DECISION RULE: call this tool whenever a port_name is required "
        "by another tool (e.g. add_model_port_to_signal_chain, auto_connect_matching_io_function_blocks_to_model_ports) "
        "but the exact identifier is unknown or ambiguous. "
        "TRIGGER PHRASES: 'list ports of <model>', 'what ports does <model> have', 'show model port "
        "blocks of <model>', or implicitly when the user names a port that may not exist. "
        "WHAT IT RETURNS: the names of all model port blocks (data port blocks, runnable function "
        "blocks, configuration port blocks, etc.) available for the given model in the active "
        "application. The returned names are the exact identifiers expected as `port_name` by "
        "add_model_port_to_signal_chain. "
        "Read-only — does not modify the signal chain or the model."
    ),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "application", "model")
async def list_model_ports(input: ListModelPortsInput) -> str:
    return await svc.list_model_ports(input.model_name)
