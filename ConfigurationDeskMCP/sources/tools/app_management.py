# -*- coding: utf-8 -*-
"""Application management tools for ConfigurationDesk MCP Server."""

from sources.models.app_management_inputs import (
    ActivateApplicationInput,
    AddApplicationInput,
    RemoveApplicationInput,
)
from sources.server.app import mcp
from sources.services import app_management_service as svc


@mcp.tool(
    name="add_application",
    description=(
        "Add a new application to the active project and activate it. "
        "PREREQUISITE: A project must be open (call create_project or open_project first). "
        "An application is required before adding bus configurations, models, or hardware. "
        "The application is automatically activated after creation."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def add_application(input: AddApplicationInput) -> str:
    return await svc.add_application(input.name)


@mcp.tool(
    name="activate_application",
    description="Activate an existing application by name",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def activate_application(input: ActivateApplicationInput) -> str:
    return await svc.activate_application(input.name)


@mcp.tool(
    name="remove_application",
    description="Remove an application from the project",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def remove_application(input: RemoveApplicationInput) -> str:
    return await svc.remove_application(input.name)


@mcp.tool(
    name="list_applications",
    description="List all applications in the active project",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def list_applications() -> str:
    return await svc.list_applications()
