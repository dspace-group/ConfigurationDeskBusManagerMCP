# -*- coding: utf-8 -*-
"""I/O Functions Library tools for ConfigurationDesk MCP Server."""

from sources.models.io_functions_inputs import (
    AddIoFunctionBlockInput,
    ConnectFunctionBlockPortToModelPortInput,
    ListIoFunctionBlockTypesInput,
)
from sources.server.app import mcp
from sources.server.preconditions import with_preconditions
from sources.services import io_functions_service as svc


@mcp.tool(
    name="add_io_function_block",
    description=(
        "[I/O FUNCTIONS] Add an analog/digital I/O function block from the "
        "I/O Functions Library to the signal chain. "
        "Examples of function_type_name: 'Voltage Out', 'Voltage In', "
        "'PWM Out', 'Digital In'. "
        "NOT for CAN/LIN/Ethernet — use `create_io_function_block` for those. "
        "DISCOVERY: Call `list_io_function_block_types` first to enumerate "
        "valid function_type_name values for the current project."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "application")
async def add_io_function_block(input: AddIoFunctionBlockInput) -> str:
    return await svc.add_io_function_block(
        input.function_type_name,
        input.block_name,
    )


@mcp.tool(
    name="list_io_function_block_types",
    description=(
        "[I/O FUNCTIONS] List the I/O function block types available in the "
        "I/O Functions Library (e.g. 'Voltage Out', 'Voltage In', 'PWM Out', "
        "'Digital In'). Use the returned names as `function_type_name` for "
        "`add_io_function_block`. "
        "NOT for listing CAN/LIN/Ethernet bus function blocks."
    ),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "application")
async def list_io_function_block_types(input: ListIoFunctionBlockTypesInput) -> str:
    return await svc.list_io_function_block_types()


@mcp.tool(
    name="connect_function_block_port_to_model_port",
    description=(
        "[SIGNAL CHAIN] Connect (map) a single named port of a function block "
        "instance to a model port of a named model port block in the signal "
        "chain. By default the first model port of the block is used; pass "
        "`model_port_name` (e.g. 'Output') to select a specific model port, "
        "which is required when several model port blocks share the same name "
        "at the same hierarchy level. Model port blocks can be nested in "
        "subsystems: if the block name exists at several hierarchy levels the "
        "tool refuses to guess — ask the user which block they mean, then pass "
        "its full hierarchy path (e.g. 'MyModel/Subsystem/Wavetable') as "
        "`model_port_block_name`. "
        "Output function blocks (e.g. 'Voltage Out') connect to model outports; "
        "input function blocks (e.g. 'Voltage In') connect to model inports. "
        "Use this for fine-grained, one-pair connections (e.g. connect "
        "function block 'Voltage Out' port 'Voltage' to model 'SineWaves' "
        "model port block 'Sine_t'). "
        "Prerequisites: the function block must already exist (see "
        "`add_io_function_block`) and the model must already be added "
        "(see `add_model`); use `list_model_port_blocks` to discover valid "
        "model port block names and `list_model_ports` for model port names "
        "and directions. "
        "For bulk auto-matching of all bus-configuration function ports to "
        "model port blocks, use `auto_connect_io_blocks_to_model_port_blocks` instead."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def connect_function_block_port_to_model_port(
    input: ConnectFunctionBlockPortToModelPortInput,
) -> str:
    return await svc.connect_function_block_port_to_model_port(
        input.function_block_name,
        input.function_block_port_name,
        input.model_name,
        input.model_port_block_name,
        input.model_port_name,
    )
