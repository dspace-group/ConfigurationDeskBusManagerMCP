"""Shared exact MCP inventory fixture helpers."""

from __future__ import annotations

import json
from pathlib import Path


_INVENTORY_PATH = Path(__file__).with_name("mcp_inventory.json")


def expected_inventory() -> dict[str, tuple[str, ...]]:
    """Return the reviewed public MCP names in deterministic order."""
    raw_inventory = json.loads(_INVENTORY_PATH.read_text(encoding="utf-8"))
    return {item_type: tuple(sorted(names)) for item_type, names in raw_inventory.items()}
