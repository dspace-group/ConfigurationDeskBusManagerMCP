# -*- coding: utf-8 -*-
"""Bus access tools for ConfigurationDesk MCP Server."""

from typing import Annotated

from pydantic import Field
from sources.server.app import mcp
from sources.server.preconditions import with_preconditions
from sources.services._pagination import DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT
from sources.services import bus_access_service as svc


@mcp.tool(
    name="create_io_function_block",
    description=(
        "[HARDWARE I/O] Create an I/O function block in the I/O Function Library. "
        "NOT for creating bus configurations — use `create_bus_configuration` for that. "
        "This creates a HARDWARE bridge between bus access requests and physical channels. "
        "BUS TYPES: 'CAN' (CAN/CAN-FD), 'LIN', 'Ethernet'. "
        "NAMING: Use descriptive names matching the cluster, e.g. 'CAN_EngineCluster', 'LIN_Door'. "
        "WORKFLOW after creation: "
        "1. set_io_function_block_property to set BaudRate. "
        "2. assign_bus_access to connect bus access requests to this function block. "
        "3. list_assignable_channel_sets + assign_channel_set for hardware channel assignment. "
        "Create ONE function block per physical bus channel (cluster). "
        "PREREQUISITE: A bus configuration must exist first (call create_bus_configuration)."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "application", "bus_config")
async def create_io_function_block(
    name: Annotated[
        str,
        Field(
            description="Descriptive name for the function block, e.g. 'CAN_Engine', 'LIN_Door', 'CANFD_Body'. Use cluster or channel name.",
        ),
    ],
    bus_type: Annotated[
        str,
        Field(
            description="Bus type: 'CAN' (for CAN and CAN-FD), 'LIN', or 'Ethernet'",
        ),
    ] = "CAN",
) -> str:
    return await svc.create_bus_function_block(name, bus_type)


@mcp.tool(
    name="set_io_function_block_property",
    description=(
        "[HARDWARE I/O] Set a property on an I/O function block. "
        "NOT related to bus configurations — this configures hardware I/O blocks. "
        "COMMON PROPERTIES: "
        "- 'BaudRate': CAN=500000, CAN-FD arbitration=500000, LIN=19200. "
        "- 'DataPhaseBaudRate': CAN-FD data phase=2000000 or 4000000. "
        "- 'Termination': 0=off, 1=on (enable bus termination resistor). "
        "- 'TransceiverType': hardware-specific transceiver setting. "
        "Use list_io_function_block_properties to discover all available properties."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project")
async def set_io_function_block_property(
    function_block_name: Annotated[
        str,
        Field(
            description="Name of the function block to configure, e.g. 'CAN_Engine'",
        ),
    ],
    property_name: Annotated[
        str,
        Field(
            description="Property name. Common: 'BaudRate' (CAN:500000, LIN:19200), 'DataPhaseBaudRate' (CAN-FD:2000000/4000000), 'Termination' (0/1)",
        ),
    ],
    value: Annotated[
        str,
        Field(
            description="Property value as string, e.g. '500000', '19200', '4000000', '0'",
        ),
    ],
    bus_type: Annotated[
        str,
        Field(
            description="Bus type: 'CAN', 'LIN', or 'Ethernet'",
        ),
    ] = "CAN",
) -> str:
    return await svc.set_bus_function_block_property(
        function_block_name,
        property_name,
        value,
        bus_type,
    )


@mcp.tool(
    name="list_io_function_block_properties",
    description=(
        "[HARDWARE I/O] List all configurable properties on an I/O function block with their current values. "
        "Returns property names, types, current values, and allowed ranges. "
        "Use this to discover available settings before calling set_io_function_block_property."
    ),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project")
async def list_io_function_block_properties(
    function_block_name: Annotated[
        str,
        Field(
            description="Name of the function block, e.g. 'CanPowertrainCluster'",
        ),
    ],
    bus_type: Annotated[
        str,
        Field(
            description="Bus type, e.g. 'CAN'",
        ),
    ] = "CAN",
) -> str:
    return await svc.list_bus_function_block_properties(
        function_block_name,
        bus_type,
    )


@mcp.tool(
    name="list_bus_access_requests",
    description=(
        "List all bus access requests across bus configurations. "
        "Bus access requests are automatically created when ECUs are assigned to bus configurations. "
        "Each cluster in each bus config part (Simulated ECUs, Inspection, Manipulation) generates one request. "
        "Format: 'Bus Access Request [BusConfigName\\Part\\ClusterName\\MatrixName]'. "
        "Optionally filter by bus_config_name to see requests for a specific configuration. "
        "These requests must be assigned to function blocks via assign_bus_access. "
        "Results are paginated; call again with next_offset to retrieve later pages."
    ),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def list_bus_access_requests(
    bus_config_name: Annotated[
        str | None,
        Field(
            description="Limit to a specific bus configuration, e.g. 'CAN_Config_1'",
        ),
    ] = None,
    offset: Annotated[
        int,
        Field(
            ge=0,
            description="Zero-based result offset. Use next_offset from the previous response.",
        ),
    ] = 0,
    limit: Annotated[
        int,
        Field(
            ge=1,
            le=MAX_PAGE_LIMIT,
            description="Maximum results per page. Defaults to 100; maximum 1000.",
        ),
    ] = DEFAULT_PAGE_LIMIT,
) -> str:
    return await svc.list_bus_access_requests(bus_config_name, offset, limit)


@mcp.tool(
    name="assign_bus_access",
    description=(
        "[HARDWARE I/O] Assign bus access requests in bus configurations to an I/O function block. "
        "The function block must be created first with create_io_function_block. "
        "Optionally scope to a specific bus_config_name and/or cluster_name. "
        "This sets the 'Bus access' property on each BusAccessRequest to the function block name."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "bus_config")
async def assign_bus_access(
    function_block_name: Annotated[
        str,
        Field(
            description="Name of the function block to assign bus access requests to, e.g. 'LinDoorFB'",
        ),
    ],
    bus_config_name: Annotated[
        str | None,
        Field(
            description="Limit to a specific bus configuration, e.g. 'BusConfig1'",
        ),
    ] = None,
    cluster_name: Annotated[
        str | None,
        Field(
            description="Limit to a specific communication cluster, e.g. 'LinDoorCluster'",
        ),
    ] = None,
) -> str:
    return await svc.assign_bus_access(
        function_block_name,
        bus_config_name,
        cluster_name,
    )


@mcp.tool(
    name="list_assignable_channel_sets",
    description=(
        "List hardware channel sets that can be assigned to a bus I/O function block. "
        "Returns available channels with their index, name, and properties. "
        "Use the index from the result in assign_channel_set to make the assignment."
    ),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "application", "hardware_topology")
async def list_assignable_channel_sets(
    function_block_name: Annotated[
        str,
        Field(
            description="Name of the function block, e.g. 'CanPowertrainCluster'",
        ),
    ],
    bus_type: Annotated[
        str,
        Field(
            description="Bus type, e.g. 'CAN'",
        ),
    ] = "CAN",
) -> str:
    return await svc.list_assignable_channel_sets(
        function_block_name,
        bus_type,
    )


@mcp.tool(
    name="assign_channel_set",
    description=(
        "Assign a specific hardware channel set to a bus I/O function block. "
        "Use list_assignable_channel_sets first to get available channel_set_index values. "
        "The channel set connects the function block to a physical hardware channel."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "application", "hardware_topology")
async def assign_channel_set(
    function_block_name: Annotated[
        str,
        Field(
            description="Name of the function block, e.g. 'CanPowertrainCluster'",
        ),
    ],
    channel_set_index: Annotated[
        int,
        Field(
            description="Index of the channel set, e.g. 0",
        ),
    ] = 0,
    bus_type: Annotated[
        str,
        Field(
            description="Bus type, e.g. 'CAN'",
        ),
    ] = "CAN",
) -> str:
    return await svc.assign_channel_set(
        function_block_name,
        channel_set_index,
        bus_type,
    )


@mcp.tool(
    name="auto_assign_channel_set",
    description=(
        "Auto-assign the best matching hardware channel set to a bus I/O function block. "
        "Uses ConfigurationDesk's algorithm to find the optimal channel. "
        "Simpler than manual list_assignable_channel_sets + assign_channel_set. "
        "Requires hardware platform to be registered first via add_hardware_platform."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "application", "hardware_topology")
async def auto_assign_channel_set(
    function_block_name: Annotated[
        str,
        Field(
            description="Name of the function block, e.g. 'CanPowertrainCluster'",
        ),
    ],
    bus_type: Annotated[
        str,
        Field(
            description="Bus type, e.g. 'CAN'",
        ),
    ] = "CAN",
) -> str:
    return await svc.auto_assign_channel_set(
        function_block_name,
        bus_type,
    )


@mcp.tool(
    name="assign_hardware_automatically",
    description=(
        "Automatically assign all hardware resources (channel sets) to all I/O function blocks. "
        "Use this as a quick alternative to manual list_assignable_channel_sets + assign_channel_set. "
        "Requires that hardware has been added with add_hardware_platform first."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "application", "hardware_topology")
async def assign_hardware_automatically() -> str:
    return await svc.assign_hardware_automatically()


@mcp.tool(
    name="auto_connect_matching_io_function_blocks_to_model_ports",
    description=(
        "Automatically connect I/O function block ports to model port blocks by name matching. "
        "Calls Algorithms.ConnectIOFunctionBlocksToModelPortBlocks(items) where items are the "
        "bus I/O function blocks present in the project. "
        "Call AFTER: add_model, create_application_process, and ensuring the model ports are "
        "in the signal chain (add_model_to_signal_chain or add_model_port_to_signal_chain). "
        "Do NOT treat generate_bus_containers as a prerequisite for this tool; only generate "
        "containers when the user explicitly asks for them. Verification queries the Links relation."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "application", "model", "application_process")
async def auto_connect_matching_io_function_blocks_to_model_ports() -> str:
    return await svc.auto_connect_matching_io_function_blocks_to_model_ports()


@mcp.tool(
    name="create_preconfigured_application_process",
    description=(
        "Create a pre-configured application process for one specific model. "
        "Calls Algorithms.CreatePreConfiguredApplicationProcessAutomatically([model], None). "
        "A new ProcessingUnitApplication is created automatically when no Parent is supplied "
        "(VEOS workflows: ensure `add_application_processing_unit` was called first). "
        "For all-models behavior, prefer create_application_process or pass `model_names` to it."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "application", "model")
async def create_preconfigured_application_process(
    model_name: Annotated[
        str,
        Field(
            description=(
                "Name of the model to create a pre-configured application process for. "
                "Use list_models to inspect available models."
            ),
        ),
    ],
) -> str:
    return await svc.create_preconfigured_application_process(model_name)
