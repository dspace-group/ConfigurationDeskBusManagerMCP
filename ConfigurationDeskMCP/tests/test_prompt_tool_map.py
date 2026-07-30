# -*- coding: utf-8 -*-
"""Keeps the public tool-to-prompt map aligned with registered MCP tools."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytest.importorskip("mcp")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TOOL_MAP = _REPO_ROOT / "docs" / "prompts" / "tool-map.md"
_TOOL_ROW = re.compile(r"^\| `([a-z][a-z0-9_]*)` \| [^|]+ \| [^|]+ \| (.+) \|$")


def test_tool_map_lists_each_registered_tool_once():
    import sources.server.app  # noqa: F401
    from sources.server import registry

    map_rows = [
        (match.group(1), match.group(2).strip())
        for line in _TOOL_MAP.read_text(encoding="utf-8").splitlines()
        if (match := _TOOL_ROW.match(line))
    ]
    mapped_tools = [tool_name for tool_name, _ in map_rows]

    assert "| Tool | Domain | Start with | Example request |" in _TOOL_MAP.read_text(
        encoding="utf-8"
    )
    assert len(mapped_tools) == len(set(mapped_tools)), "Tool map contains duplicate tool rows."
    assert set(mapped_tools) == set(registry.registered_tool_names())
    assert all(example for _, example in map_rows), "Each tool must have an example request."
