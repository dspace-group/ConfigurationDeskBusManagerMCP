# -*- coding: utf-8 -*-
"""Working view and conflict tools for ConfigurationDesk MCP Server."""

from sources.models.working_view_inputs import (
    CreateWorkingViewInput,
    ExportWorkingViewInput,
    RemoveWorkingViewInput,
)
from sources.server.app import mcp
from sources.server.preconditions import with_preconditions
from sources.services import working_view_service as svc


@mcp.tool(
    name="create_working_view",
    description=(
        "Create a working view to visualize and organize signal chain elements. "
        "Working views show the connections between bus function ports, I/O blocks, and model ports. "
        "Useful for reviewing the configuration graphically."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "application")
async def create_working_view(input: CreateWorkingViewInput) -> str:
    return await svc.create_working_view(input.name)


@mcp.tool(
    name="list_working_views",
    description="List all working views in the project with their names and element counts",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "application")
async def list_working_views() -> str:
    return await svc.list_working_views()


@mcp.tool(
    name="remove_working_view",
    description="Remove a working view by name",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "application")
async def remove_working_view(input: RemoveWorkingViewInput) -> str:
    return await svc.remove_working_view(input.name)


@mcp.tool(
    name="clear_all_working_views",
    description="Remove all working views from the project",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "application")
async def clear_all_working_views() -> str:
    return await svc.clear_all_working_views()


@mcp.tool(
    name="export_working_view",
    description="Export a working view's signal chain to a file on disk",
    annotations={
        # Not read-only: writes an export file to the filesystem (like backup_project).
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "application")
async def export_working_view(input: ExportWorkingViewInput) -> str:
    return await svc.export_working_view(input.name, input.path)


@mcp.tool(
    name="check_conflicts",
    description=(
        "Export and analyze all configuration conflicts in the project. "
        "Returns a list of conflicts with name, context, property, current value, "
        "suggested values, and effect. Use this after assigning matrix elements, "
        "features, hardware, or bus access to identify and resolve issues. "
        "IMPORTANT: Always call this before building to ensure the configuration is valid."
    ),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "application")
async def check_conflicts() -> str:
    return await svc.check_conflicts()
