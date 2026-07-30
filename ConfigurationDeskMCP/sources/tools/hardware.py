# -*- coding: utf-8 -*-
"""Hardware management tools for ConfigurationDesk MCP Server."""

from typing import Annotated

from pydantic import Field
from sources.server.app import mcp
from sources.server.preconditions import with_preconditions
from sources.services import hardware_service as svc


@mcp.tool(
    name="add_hardware_platform",
    description=(
        "Register a supported hardware platform and scan its topology. "
        "BEFORE calling this tool, ASK the user which hardware approach they want: "
        "1) Provide address of SCALEXIO, MicroAutoBox III, or MicroLabBox II hardware → use this tool, "
        "2) Import an .htfx topology file → use import_hardware_topology, "
        "3) Create empty topology (VEOS/no hardware) → use add_application_processing_unit. "
        "VEOS is NOT a platform - never call this for VEOS. "
        "Returns the unique platform name for subsequent hardware operations."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@with_preconditions("connection", "project", "application")
async def add_hardware_platform(
    ip_addresses: Annotated[
        list[str],
        Field(
            description="IP address(es) of the platform to register, e.g. ['192.0.2.10']",
        ),
    ],
    platform_type: Annotated[
        str,
        Field(
            description="Platform type: 'SCALEXIO', 'MicroAutoBox III', or 'MicroLabBox II'. VEOS is not a platform.",
        ),
    ] = "SCALEXIO",
) -> str:
    return await svc.add_hardware_platform(ip_addresses, platform_type)


@mcp.tool(
    name="import_hardware_topology",
    description=(
        "Import a hardware topology from an .htfx file. "
        "Use when user has a pre-exported hardware topology file. "
        "ASK the user for the full path to the .htfx file before calling."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "application")
async def import_hardware_topology(
    path: Annotated[
        str,
        Field(
            description="Path to the hardware topology file (.htfx), e.g. 'C:/HW/topology.htfx'",
        ),
    ],
) -> str:
    return await svc.import_hardware_topology(path)


@mcp.tool(
    name="scan_hardware",
    description=(
        "Re-scan a registered hardware platform to refresh its topology. "
        "Use when hardware configuration changed (boards added/removed) since registration. "
        "Requires platform_name from add_hardware_platform or list_platforms."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@with_preconditions("connection", "project", "application")
async def scan_hardware(
    platform_name: Annotated[
        str,
        Field(
            description="Unique name of the registered platform to scan, e.g. 'SCALEXIO Processing Unit at 192.0.2.10'",
        ),
    ],
) -> str:
    return await svc.scan_hardware(platform_name)


@mcp.tool(
    name="remove_hardware",
    description="Remove a hardware platform from the project",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "application")
async def remove_hardware(
    name: Annotated[
        str,
        Field(
            description="Name or wildcard pattern of hardware element(s) to remove, e.g. 'SCALEXIO*' or 'MicroLabBox*'",
        ),
    ],
) -> str:
    return await svc.remove_hardware(name)


@mcp.tool(
    name="list_platforms",
    description="List all hardware platforms in the project",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def list_platforms() -> str:
    return await svc.list_platforms()


@mcp.tool(
    name="refresh_platforms",
    description="Refresh hardware platform information",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def refresh_platforms() -> str:
    return await svc.refresh_platforms()


@mcp.tool(
    name="add_hardware_element",
    description="Add a hardware element to a platform",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "application")
async def add_hardware_element(
    element_type: Annotated[
        str,
        Field(
            description="Type of hardware element to add, e.g. 'SCALEXIO Processing Unit' or 'DS6311'",
        ),
    ],
) -> str:
    return await svc.add_hardware_element(element_type)


@mcp.tool(
    name="add_application_processing_unit",
    description=(
        "Add a ProcessingUnitApplication to the application configuration. "
        "Use this for VEOS-targeted or no-hardware workflows where the project needs "
        "an application processing unit to host I/O function blocks and application processes. "
        "VEOS does NOT use registered hardware platforms; it consumes generated Bus "
        "Simulation Containers (BSC)."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "application")
async def add_application_processing_unit() -> str:
    return await svc.add_application_processing_unit()
