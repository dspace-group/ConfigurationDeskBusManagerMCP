# -*- coding: utf-8 -*-
"""Application lifecycle tools for ConfigurationDesk MCP Server."""

from sources.models.application_inputs import (
    StartConfigurationDeskInput,
    StopConfigurationDeskInput,
)
from sources.server.app import mcp
from sources.services import application_service as svc


@mcp.tool(
    name="start_configurationdesk",
    description=(
        "MUST be called first before any other tool. "
        "Starts the ConfigurationDesk application and establishes a COM connection. "
        "Idempotent: safe to call if already running. "
        "After this, use set_project_root and create_project to begin work."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def start_configurationdesk(input: StartConfigurationDeskInput) -> str:
    return await svc.start(visible=input.visible)


@mcp.tool(
    name="stop_configurationdesk",
    description="Close ConfigurationDesk application, optionally saving work",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def stop_configurationdesk(input: StopConfigurationDeskInput) -> str:
    return await svc.stop(save=input.save)


@mcp.tool(
    name="get_application_status",
    description=(
        "Get current ConfigurationDesk application status "
        + "including project name, project root, and application name"
    ),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def get_application_status() -> str:
    return await svc.get_status()


@mcp.tool(
    name="save_project",
    description="Save the current ConfigurationDesk project",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def save_project() -> str:
    return await svc.save_project()


@mcp.tool(
    name="undo",
    description=(
        "Undo the last action in ConfigurationDesk. Reverses the most recent modeling "
        "change (e.g. removes an element that was just added, or re-adds one that was "
        "removed). Not supported for file-system actions such as creating projects."
    ),
    annotations={
        "readOnlyHint": False,
        # Destructive: undo can reverse an add, removing elements from the configuration.
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def undo() -> str:
    return await svc.undo()


@mcp.tool(
    name="redo",
    description=(
        "Redo the last undone action in ConfigurationDesk. Re-applies a change that was "
        "reversed by undo (which can re-remove an element). Not supported for file-system "
        "actions such as creating projects."
    ),
    annotations={
        "readOnlyHint": False,
        # Destructive: redo can re-apply a removal, deleting elements again.
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def redo() -> str:
    return await svc.redo()


@mcp.tool(
    name="diagnose_connection",
    description=(
        "Run diagnostic checks on the COM connection environment. "
        "Call this when start_configurationdesk fails to understand WHY. "
        "Checks: pywin32 installed, ConfigurationDesk COM registration, "
        "running instance detection, dynamic dispatch availability, "
        "and current bridge state. Returns a structured report."
    ),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def diagnose_connection() -> str:
    return await svc.diagnose_connection()
