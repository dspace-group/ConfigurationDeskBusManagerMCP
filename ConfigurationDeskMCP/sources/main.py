# SPDX-License-Identifier: Apache-2.0
# Copyright (c) dSPACE Group SE & Co. KG.
"""Entry point for the ConfigurationDesk MCP server.

Transport is selected from the ``MCP_TRANSPORT`` environment variable
(default: ``stdio``). Streamable HTTP requires explicit opt-in and is restricted
to loopback hosts. A small CLI surface allows inspecting the registered tool set
without launching a host.
"""

from __future__ import annotations

import argparse
import asyncio
import inspect

from sources.config.settings import get_settings
from sources.server.app import mcp
from sources.utils.logger import get_logger

_log = get_logger(__name__)


def _build_run_kwargs(run_callable, cfg) -> dict[str, object]:
    run_kwargs: dict[str, object] = {"transport": cfg.mcp_transport}
    if cfg.mcp_transport != "streamable-http":
        return run_kwargs

    try:
        params = inspect.signature(run_callable).parameters
    except (TypeError, ValueError):
        return run_kwargs

    if "host" in params:
        run_kwargs["host"] = cfg.mcp_host
    if "port" in params:
        run_kwargs["port"] = cfg.mcp_port
    return run_kwargs


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="configurationdesk-mcp",
        description="dSPACE ConfigurationDesk / BusManager MCP server.",
    )
    parser.add_argument(
        "--list-tools",
        action="store_true",
        help="Print the names of all registered tools and exit.",
    )
    parser.add_argument(
        "--list-resources",
        action="store_true",
        help="Print the URIs of all registered resources and exit.",
    )
    parser.add_argument(
        "--list-prompts",
        action="store_true",
        help="Print the names of all registered prompts and exit.",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print the server version and exit.",
    )
    return parser.parse_args(argv)


def _print_tools() -> None:
    from sources.server.registry import registered_tool_names  # noqa: PLC0415

    for name in registered_tool_names():
        print(name)


def _print_resources() -> None:
    for resource in sorted(asyncio.run(mcp.list_resources()), key=lambda item: str(item.uri)):
        print(resource.uri)


def _print_prompts() -> None:
    for prompt in sorted(asyncio.run(mcp.list_prompts()), key=lambda item: item.name):
        print(prompt.name)


def main(argv: list[str] | None = None) -> None:
    """Start the MCP server, or handle a CLI inspection command."""
    args = _parse_args(argv)
    cfg = get_settings()

    if args.version:
        print(cfg.server_version)
        return
    if args.list_tools:
        _print_tools()
        return
    if args.list_resources:
        _print_resources()
        return
    if args.list_prompts:
        _print_prompts()
        return

    _log.debug("Starting with transport=%s", cfg.mcp_transport)
    mcp.run(**_build_run_kwargs(mcp.run, cfg))
