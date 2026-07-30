# -*- coding: utf-8 -*-
"""Public MCP contract checks for registered tools and response envelopes."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from tests._mcp_inventory import expected_inventory
from sources.tools._responses import error_response, success_response

pytest.importorskip("mcp")


_REQUIRED_ANNOTATIONS = {
    "readOnlyHint",
    "destructiveHint",
    "idempotentHint",
    "openWorldHint",
}
_TOOL_NAME = re.compile(r"[a-z][a-z0-9_]*\Z")
_PAGINATED_TOOL_NAMES = {
    "list_bus_access_requests",
    "find_bus_config_elements",
    "list_matrices",
    "find_matrix_elements",
    "list_configuration",
}
_CONDITIONALLY_DESTRUCTIVE_TOOL_NAMES = {
    "create_project",
    "open_project_from_backup",
    "build_application",
}
_REPO_ROOT = Path(__file__).resolve().parents[2]
_INVENTORY_DOCUMENTS = {
    _REPO_ROOT / "README.md": ("tools", "resources", "prompts"),
    _REPO_ROOT / "ARCHITECTURE.md": ("tools", "resources", "prompts"),
    _REPO_ROOT / "docs" / "README.md": ("tools",),
    _REPO_ROOT / "docs" / "prompts" / "README.md": ("tools", "prompts"),
    _REPO_ROOT / "docs" / "tools" / "README.md": ("tools",),
}


def _annotation_mapping(tool: Any) -> Mapping[str, Any]:
    annotations = getattr(tool, "annotations", None)
    if annotations is None:
        return {}
    if isinstance(annotations, Mapping):
        return annotations
    model_dump = getattr(annotations, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        if isinstance(dumped, Mapping):
            return dumped
    return vars(annotations)


def test_registered_tools_have_public_mcp_metadata():
    import sources.server.app  # noqa: F401
    from sources.server.app import mcp

    tools = asyncio.run(mcp.list_tools())

    assert len(tools) == len(expected_inventory()["tools"])
    for tool in tools:
        assert _TOOL_NAME.fullmatch(tool.name), tool.name
        assert isinstance(tool.description, str) and tool.description.strip(), tool.name
        assert "\n" not in tool.description, tool.name

        annotations = _annotation_mapping(tool)
        assert _REQUIRED_ANNOTATIONS <= set(annotations), tool.name
        assert all(isinstance(annotations[name], bool) for name in _REQUIRED_ANNOTATIONS)

        input_schema = getattr(tool, "inputSchema", None)
        assert isinstance(input_schema, Mapping), tool.name
        assert input_schema.get("type") == "object", tool.name


def test_registered_resources_have_required_mcp_metadata():
    import sources.server.app  # noqa: F401
    from sources.server.app import mcp

    resources = asyncio.run(mcp.list_resources())

    assert resources
    for resource in resources:
        assert isinstance(resource.name, str) and resource.name.strip()
        assert isinstance(resource.title, str) and resource.title.strip(), resource.name
        assert str(resource.uri).strip(), resource.name
        assert isinstance(resource.mimeType, str) and resource.mimeType.strip(), resource.name


def test_documented_inventory_matches_live_mcp_registry():
    import sources.server.app  # noqa: F401
    from sources.server.app import mcp

    inventory = {
        "tools": len(asyncio.run(mcp.list_tools())),
        "resources": len(asyncio.run(mcp.list_resources())),
        "prompts": len(asyncio.run(mcp.list_prompts())),
    }

    for document, item_types in _INVENTORY_DOCUMENTS.items():
        text = document.read_text(encoding="utf-8")
        for item_type in item_types:
            count = inventory[item_type]
            assert re.search(rf"\b{count}\s+(?:MCP\s+)?{item_type}\b", text), document


def test_large_read_tools_publish_pagination_parameters():
    import sources.server.app  # noqa: F401
    from sources.server.app import mcp

    tools = {tool.name: tool for tool in asyncio.run(mcp.list_tools())}

    for tool_name in _PAGINATED_TOOL_NAMES:
        properties = tools[tool_name].inputSchema["properties"]
        assert {"offset", "limit"} <= set(properties), tool_name


def test_all_tool_schema_titles_match_public_tool_names():
    import sources.server.app  # noqa: F401
    from sources.server.app import mcp

    tools = asyncio.run(mcp.list_tools())

    for tool in tools:
        assert tool.inputSchema["title"] == f"{tool.name}Arguments", tool.name
        assert tool.outputSchema["title"] == f"{tool.name}Output", tool.name


def test_conditionally_destructive_tools_publish_destructive_hints():
    import sources.server.app  # noqa: F401
    from sources.server.app import mcp

    tools = {tool.name: tool for tool in asyncio.run(mcp.list_tools())}

    for tool_name in _CONDITIONALLY_DESTRUCTIVE_TOOL_NAMES:
        annotations = _annotation_mapping(tools[tool_name])
        assert annotations["readOnlyHint"] is False, tool_name
        assert annotations["destructiveHint"] is True, tool_name


def test_registered_tools_have_domain_contract_coverage():
    import sources.server.app  # noqa: F401
    from sources.server import registry
    from tests.domains.test_tool_coverage import _covered_tool_names

    assert set(registry.registered_tool_names()) == set(_covered_tool_names())


def test_response_helpers_keep_machine_parseable_contracts():
    success = json.loads(success_response(message="ok", verified=True))
    error = json.loads(error_response("failed", error_code="TEST_FAILURE"))

    assert success["success"] is True
    assert success["verified"] is True
    assert error["success"] is False
    assert error["error_code"] == "TEST_FAILURE"
    assert isinstance(error["retryable"], bool)
    assert error["recovery_hint"]
    assert error["next_action"]
