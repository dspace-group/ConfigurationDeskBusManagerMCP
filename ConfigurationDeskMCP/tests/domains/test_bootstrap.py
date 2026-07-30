# -*- coding: utf-8 -*-
"""Server bootstrap contract checks."""

import asyncio

from sources.server.app import mcp

COVERS: tuple[str, ...] = ()


def test_redundant_connectivity_probe_tools_are_not_registered():
    tool_names = {tool.name for tool in asyncio.run(mcp.list_tools())}
    assert tool_names.isdisjoint({"health", "echo"})
