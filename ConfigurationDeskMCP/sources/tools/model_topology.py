# -*- coding: utf-8 -*-
"""Model topology tools for ConfigurationDesk MCP Server."""

from typing import Annotated

from pydantic import Field

from sources.models.model_topology_inputs import (
    AddModelInput,
    AddModelPortBlockToSignalChainInput,
    AddModelToSignalChainInput,
    ListModelPortBlocksInput,
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
        "SUPPORTED FORMATS: .slx/.mdl (Simulink), .sic (Simulink implementation container), .bsc (Bus Simulation Container), "
        ".fmu (Functional Mock-up Unit). "
        "For .sic/.bsc/.fmu files, analysis is skipped since ports are already defined. "
        "For Simulink models, set analyze=true (default) to detect model ports. "
        "WORKFLOW: add_model → analyze_models → create_application_process → "
        "auto_connect_io_blocks_to_model_port_blocks. "
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
        "Call after add_model and before auto_connect_io_blocks_to_model_port_blocks. "
        "Not needed for .sic/.bsc/.fmu files (already analyzed). May take time for large models."
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
        "name is given, use add_model_port_block_to_signal_chain instead. "
        "TRIGGER PHRASES: 'add model <name> to signal chain', 'add all ports of <model> to signal "
        "chain', 'expose model <name> in signal chain', 'enable all model port blocks of <model>'. "
        "WHAT IT DOES: sets IsInApplication=True on EVERY model port block belonging to the named "
        "model, exposing all of them in the logical signal chain so they can later be wired to "
        "function blocks (e.g. via auto_connect_io_blocks_to_model_port_blocks). A model port block is "
        "the graphical representation of the ConfigurationDesk model interface in the signal chain. "
        "INPUT: model_name only — do NOT pass a port block name. "
        "DOES NOT: add behavior models (use add_model), create connections "
        "(use auto_connect_io_blocks_to_model_port_blocks), or remove port blocks from the chain. "
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
    name="add_model_port_block_to_signal_chain",
    description=(
        "[SIGNAL CHAIN — SELECTIVE] DECISION RULE: pick this tool whenever the user names a SPECIFIC "
        "model port block (e.g. 'Sine_t', 'Throttle_In') alongside its model. If no port block "
        "name is given, use add_model_to_signal_chain (BULK) instead. "
        "TRIGGER PHRASES: 'add model port block <block> of model <model> to signal chain', "
        "'add port <port> of <model> to signal chain', 'add <port> from <model> to the signal chain', "
        "'enable model port block <block> of <model>'. "
        "WHAT IT DOES: sets IsInApplication=True on the SINGLE named model port block only; all "
        "other model port blocks of the model are unaffected. A model port block is the graphical "
        "representation of the ConfigurationDesk model interface in the signal chain and contains "
        "one or more model ports of the same data direction (data port block with data inports or "
        "data outports, runnable function block, configuration port block). "
        "INPUT: model_name AND port_block_name — if the exact port_block_name is unknown, call "
        "list_model_port_blocks first to discover the valid identifiers. "
        "DOES NOT: add behavior models (use add_model), create connections "
        "(use auto_connect_io_blocks_to_model_port_blocks), or affect other port blocks of the same model. "
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
async def add_model_port_block_to_signal_chain(input: AddModelPortBlockToSignalChainInput) -> str:
    return await svc.add_model_port_block_to_signal_chain(input.model_name, input.port_block_name)


@mcp.tool(
    name="list_model_port_blocks",
    description=(
        "[SIGNAL CHAIN — DISCOVERY] DECISION RULE: call this tool whenever a model port block name "
        "is required by another tool (e.g. add_model_port_block_to_signal_chain, "
        "connect_function_block_port_to_model_port) but the exact identifier is unknown or ambiguous. "
        "TRIGGER PHRASES: 'list ports of <model>', 'what ports does <model> have', 'show model port "
        "blocks of <model>', or implicitly when the user names a port that may not exist. "
        "WHAT IT RETURNS: the names of all model port blocks (data port blocks, runnable function "
        "blocks, configuration port blocks) available for the given model in the active "
        "application. The returned names are the exact identifiers expected as `port_block_name` by "
        "add_model_port_block_to_signal_chain. "
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
async def list_model_port_blocks(input: ListModelPortBlocksInput) -> str:
    return await svc.list_model_port_blocks(input.model_name)


@mcp.tool(
    name="list_model_ports",
    description=(
        "[SIGNAL CHAIN — DISCOVERY] DECISION RULE: pick this tool when the user asks about the "
        "PORTS THEMSELVES — their direction, data type, or width. If the user needs the names of "
        "the BLOCKS (for add_model_port_block_to_signal_chain or "
        "connect_function_block_port_to_model_port), use list_model_port_blocks instead. "
        "TRIGGER PHRASES: 'what data type is port <x>', 'show the inports/outports of <model>', "
        "'how wide is model port <x>', 'list the model ports inside <block>'. "
        "WHAT IT RETURNS: one entry per model port — the individual data inport, data outport, "
        "runnable function port, or configuration port CONTAINED IN a model port block — with its "
        "owning port_block_name and the read-only properties ConfigurationDesk exposes: port_type "
        "(In/Out), data_type (e.g. Int8), data_width (vector size; 1 = scalar), signal_id, "
        "description, unit, and variable_size. Properties that do not apply to a port type are "
        "omitted. "
        "INPUT: model_name, plus optional port_block_name to restrict the listing to one block. "
        "DOES NOT: return block names usable as port_block_name (use list_model_port_blocks), and "
        "cannot change these properties — they are read-only in ConfigurationDesk and can only be "
        "changed in the behavior model. "
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
    return await svc.list_model_ports(input.model_name, input.port_block_name)
