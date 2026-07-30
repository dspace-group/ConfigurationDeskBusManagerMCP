# -*- coding: utf-8 -*-
"""Configuration (Application Processes, Tasks, Events) tools for ConfigurationDesk MCP Server."""

from typing import Annotated

from pydantic import Field

from sources.server.app import mcp
from sources.services._pagination import DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT
from sources.services import configuration_service as svc


@mcp.tool(
    name="list_configuration",
    description=(
        "List the application configuration tree "
        + "(executable applications, processing units, tasks, events). "
        + "Results are paginated; call again with next_offset to retrieve later pages."
    ),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def list_configuration(
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
    return await svc.list_configuration(offset, limit)
