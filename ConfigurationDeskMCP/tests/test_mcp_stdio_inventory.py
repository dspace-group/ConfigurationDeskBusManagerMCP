"""Verify the exact public MCP inventory over a real stdio session."""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import timedelta
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from tests._mcp_inventory import expected_inventory

pytest.importorskip("mcp")


_SERVER_ROOT = Path(__file__).resolve().parents[1]


async def _stdio_inventory() -> dict[str, tuple[str, ...]]:
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "sources"],
        cwd=_SERVER_ROOT,
        env={**os.environ, "LOG_LEVEL": "ERROR", "MCP_TRANSPORT": "stdio"},
    )

    async with stdio_client(server) as (read_stream, write_stream):
        async with ClientSession(
            read_stream,
            write_stream,
            read_timeout_seconds=timedelta(seconds=20),
        ) as session:
            await session.initialize()
            tools = await session.list_tools()
            resources = await session.list_resources()
            prompts = await session.list_prompts()

    return {
        "tools": tuple(sorted(tool.name for tool in tools.tools)),
        "resources": tuple(sorted(str(resource.uri) for resource in resources.resources)),
        "prompts": tuple(sorted(prompt.name for prompt in prompts.prompts)),
    }


def test_stdio_inventory_matches_reviewed_names():
    assert asyncio.run(_stdio_inventory()) == expected_inventory()
