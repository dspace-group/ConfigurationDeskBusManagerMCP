# -*- coding: utf-8 -*-
"""Tool, resource, and prompt registration via auto-discovery.

Importing this module registers every tool by importing each module in
``sources.tools`` (the ``@mcp.tool`` decorators run as import side effects),
then registers resources and prompts.

**The code is the control surface.** To add a tool domain, drop a new
``sources/tools/<name>.py`` module that defines ``@mcp.tool`` handlers — it is
discovered and exposed automatically. To remove one, delete the module. There is
no separate manifest or allowlist to keep in sync.

Modules whose name starts with ``_`` (e.g. ``_responses``) are treated as
helpers and skipped.
"""

from __future__ import annotations

import asyncio
import importlib
import inspect
import pkgutil

import sources.tools as _tools_pkg
from sources.server.app import mcp
from sources.utils.logger import get_logger

logger = get_logger(__name__)

_registered_modules: list[str] = []


def _discover_tool_modules() -> list[str]:
    """Return the import paths of every public module under ``sources.tools``."""
    names: list[str] = []
    for info in pkgutil.iter_modules(_tools_pkg.__path__):
        if info.ispkg or info.name.startswith("_"):
            continue
        names.append(f"{_tools_pkg.__name__}.{info.name}")
    return sorted(names)


def _register_tool_modules() -> list[str]:
    registered: list[str] = []
    for module_name in _discover_tool_modules():
        importlib.import_module(module_name)  # triggers @mcp.tool registration
        registered.append(module_name)
    return registered


def registered_tool_modules() -> list[str]:
    """Return the tool modules discovered and registered at import time."""
    return list(_registered_modules)


def _extract_tool_names(tools) -> list[str]:
    names: list[str] = []
    for tool in tools:
        name = getattr(tool, "name", None)
        if isinstance(name, str) and name:
            names.append(name)
    return sorted(set(names))


def _tool_names_from_server(server) -> list[str]:
    """Resolve tool names from a FastMCP-like server with compatibility fallbacks."""
    list_tools = getattr(server, "list_tools", None)
    if callable(list_tools):
        result = list_tools()
        if inspect.isawaitable(result):
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                return _extract_tool_names(asyncio.run(result))
            result.close()
        else:
            return _extract_tool_names(result)

    tool_manager = getattr(server, "_tool_manager", None)
    if tool_manager is None:
        return []

    manager_list_tools = getattr(tool_manager, "list_tools", None)
    if callable(manager_list_tools):
        return _extract_tool_names(manager_list_tools())

    tools = getattr(tool_manager, "_tools", {})
    if isinstance(tools, dict):
        return sorted(name for name in tools if isinstance(name, str) and name)
    return []


def registered_tool_names() -> list[str]:
    """Return the names of all currently registered tools."""
    return _tool_names_from_server(mcp)


# ── Registration sequence ─────────────────────────────────────────────────────

_registered_modules = _register_tool_modules()

# Resources
import sources.resources.domain_resources  # noqa: E402, F401

# Prompts
#   configurationdesk_prompts — the single end-to-end use-case prompt
#   individual_setup_prompts  — focused, single-task prompts per common tool
import sources.prompts.configurationdesk_prompts  # noqa: E402, F401
import sources.prompts.individual_setup_prompts  # noqa: E402, F401

logger.info(
    "Registered %d tool module(s); %d tool(s) exposed",
    len(_registered_modules),
    len(registered_tool_names()),
)
