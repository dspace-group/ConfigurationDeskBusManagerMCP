# -*- coding: utf-8 -*-
"""Auto-discovery registration tests.

These guard the "code is the control surface" model: every public module under
``sources.tools`` is discovered and registers its tools, helper modules are
skipped, and a newly added tool module shows up without touching any manifest.
The ``mcp`` SDK is required, so these are skipped when it is unavailable.
"""

import asyncio

import pytest

from tests._mcp_inventory import expected_inventory

pytest.importorskip("mcp")


def test_discovery_skips_helper_modules():
    from sources.server import registry

    modules = registry._discover_tool_modules()
    assert all(not m.rsplit(".", 1)[1].startswith("_") for m in modules)
    assert "sources.tools._responses" not in modules


def test_all_tool_modules_register_tools():
    import sources.server.app  # noqa: F401  triggers registration
    from sources.server import registry

    modules = registry.registered_tool_modules()
    # Every tool .py file under sources/tools (minus helpers) should be present.
    assert len(modules) >= 12
    # Registration must match the reviewed public inventory exactly.
    assert len(registry.registered_tool_names()) == len(expected_inventory()["tools"])


def test_listed_tools_match_registered_manager():
    import sources.server.app  # noqa: F401
    from sources.server.app import mcp
    from sources.server import registry

    public_names = {tool.name for tool in asyncio.run(mcp.list_tools())}

    assert set(registry.registered_tool_names()) == public_names


def test_registry_tool_names_fall_back_to_manager_list_tools():
    from types import SimpleNamespace

    from sources.server import registry

    fake_server = SimpleNamespace(
        _tool_manager=SimpleNamespace(
            list_tools=lambda: [
                SimpleNamespace(name="tool_a"),
                SimpleNamespace(name="tool_b"),
            ]
        )
    )

    assert registry._tool_names_from_server(fake_server) == ["tool_a", "tool_b"]
