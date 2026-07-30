# -*- coding: utf-8 -*-
"""Tool-coverage guard.

Fails when a registered MCP tool is not exercised by any per-domain test
module, or when a domain module claims to cover a tool that no longer exists.
Each ``tests/domains/test_<domain>.py`` module declares a module-level
``COVERS`` tuple of the tool names it exercises; the union must equal the set
of registered tools exactly.
"""

from __future__ import annotations

import importlib
import pkgutil

import pytest

pytest.importorskip("mcp")

import tests.domains as domains_pkg  # noqa: E402


def _covered_tool_names() -> dict[str, list[str]]:
    """Map each covered tool name → the domain modules that claim to cover it."""
    coverage: dict[str, list[str]] = {}
    for info in pkgutil.iter_modules(domains_pkg.__path__):
        if info.ispkg or info.name.startswith("_") or info.name == "test_tool_coverage":
            continue
        module = importlib.import_module(f"{domains_pkg.__name__}.{info.name}")
        for tool_name in getattr(module, "COVERS", ()):  # noqa: B009
            coverage.setdefault(tool_name, []).append(info.name)
    return coverage


def test_every_registered_tool_has_a_domain_test():
    import sources.server.app  # noqa: F401  triggers registration
    from sources.server import registry

    registered = set(registry.registered_tool_names())
    covered = set(_covered_tool_names())

    missing = sorted(registered - covered)
    orphaned = sorted(covered - registered)

    assert not missing, f"Registered tools with no per-domain test: {missing}"
    assert not orphaned, f"Domain tests reference unknown tools: {orphaned}"


def test_no_tool_is_claimed_by_multiple_domains():
    duplicates = {name: mods for name, mods in _covered_tool_names().items() if len(mods) > 1}

    assert not duplicates, f"Tools claimed by multiple domain modules: {duplicates}"
