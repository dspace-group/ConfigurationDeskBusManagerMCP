"""COM wrappers for ConfigurationDesk application configuration operations.

All functions must be called on the STA thread via dispatch().
"""

from __future__ import annotations

import logging
from typing import Any

_log = logging.getLogger(__name__)


def _walk_config(rel, node, result, depth):
    """Recursively walk the application configuration tree."""
    entry = {"name": node.Name, "depth": depth}
    try:
        entry["roles"] = list(node.Roles)
    except Exception:
        entry["roles"] = []
    result.append(entry)
    try:
        for child in rel.GetElements(node):
            _walk_config(rel, child, result, depth + 1)
    except Exception:
        pass


def list_configuration(connection) -> list[dict[str, Any]]:
    """List the application configuration tree."""
    rel = connection.relations.Item("ApplicationConfiguration")
    config: list[dict[str, Any]] = []
    for top in rel.GetTopNodes():
        _walk_config(rel, top, config, depth=0)
    return config
