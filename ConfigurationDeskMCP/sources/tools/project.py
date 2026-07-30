# -*- coding: utf-8 -*-
"""Project management tools for ConfigurationDesk MCP Server."""

from sources.models.project_inputs import (
    BackupProjectInput,
    CloseProjectInput,
    CreateProjectInput,
    OpenProjectFromBackupInput,
    OpenProjectInput,
    RemoveProjectInput,
    SetProjectRootInput,
)
from sources.server.app import mcp
from sources.services import project_service as svc


@mcp.tool(
    name="create_project",
    description=(
        "Create a new ConfigurationDesk project. Closes any active project first. "
        "PREREQUISITE: ConfigurationDesk must be running (call start_configurationdesk first). "
        "Optionally provide project_root to set the storage location "
        "(avoids needing a separate set_project_root call). "
        "Set replace=true to overwrite if a project with the same name exists. "
        "After creation, the project is automatically opened and active."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def create_project(input: CreateProjectInput) -> str:
    return await svc.create_project(input.name, input.project_root, input.replace)


@mcp.tool(
    name="open_project",
    description="Open an existing ConfigurationDesk project by name",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def open_project(input: OpenProjectInput) -> str:
    return await svc.open_project(input.name)


@mcp.tool(
    name="close_project",
    description="Close the active project, optionally saving first",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def close_project(input: CloseProjectInput) -> str:
    return await svc.close_project(input.save)


@mcp.tool(
    name="remove_project",
    description="Remove a project from ConfigurationDesk",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def remove_project(input: RemoveProjectInput) -> str:
    return await svc.remove_project(input.name, input.delete_files)


@mcp.tool(
    name="list_projects",
    description="List all projects available in the current project root",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def list_projects() -> str:
    return await svc.list_projects()


@mcp.tool(
    name="set_project_root",
    description=(
        "Set the project root directory (project location) where ConfigurationDesk stores projects. "
        "PREREQUISITE: ConfigurationDesk must be running (call start_configurationdesk first). "
        "This is OPTIONAL — ConfigurationDesk has a default project location. "
        "Only call this if you need projects stored in a specific folder. "
        "The directory will be created if it does not exist. "
        "Example path: 'C:/Users/user/Documents/dSPACE/ConfigurationDesk/2026-A (26.2)'"
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def set_project_root(input: SetProjectRootInput) -> str:
    return await svc.set_project_root(input.path)


@mcp.tool(
    name="get_project_path",
    description="Get the file path of the active project",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def get_project_path() -> str:
    return await svc.get_project_path()


@mcp.tool(
    name="backup_project",
    description="Create a backup archive of the active project on disk",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def backup_project(input: BackupProjectInput) -> str:
    return await svc.backup_project(input.path)


@mcp.tool(
    name="open_project_from_backup",
    description="Restore and open a project from a backup archive, optionally overwriting an existing project",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def open_project_from_backup(input: OpenProjectFromBackupInput) -> str:
    return await svc.open_project_from_backup(input.backup_path, input.name, input.overwrite)
