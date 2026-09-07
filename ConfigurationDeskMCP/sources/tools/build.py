# -*- coding: utf-8 -*-
"""Build management tools for ConfigurationDesk MCP Server."""

from sources.models.build_inputs import (
    BuildApplicationInput,
)
from sources.server.app import mcp
from sources.server.preconditions import with_preconditions
from sources.services import build_service as svc


@mcp.tool(
    name="build_application",
    description=(
        "Build the ConfigurationDesk real-time application. This is the FINAL step in the workflow. "
        "Compiles model code, generates the real-time application (.rta), and optionally downloads "
        "to hardware and starts execution. "
        "The build produces one real-time application per processing unit application, each executed "
        "on one processing unit (hardware). A processing unit application with a single application "
        "process yields a single-core real-time application; multiple application processes yield a "
        "multicore real-time application on multiple cores of that processing unit. "
        "PARAMETERS: "
        "- download=true: download to SCALEXIO hardware (set false if no hardware). "
        "- start=true: start real-time application after download. "
        "PREREQUISITES: All bus configurations assigned, hardware assigned, no conflicts. "
        "Call check_conflicts first to verify. Operation takes several minutes. "
        "Returns result_folder path on success."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
@with_preconditions("connection", "project", "application")
async def build_application(input: BuildApplicationInput) -> str:
    return await svc.build_application(
        input.download,
        input.start,
        input.unload,
    )


@mcp.tool(
    name="get_build_result",
    description="Get the path to the build result directory",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "application")
async def get_build_result() -> str:
    return await svc.get_build_result()
