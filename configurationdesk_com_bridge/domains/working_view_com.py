"""COM wrappers for ConfigurationDesk working view and conflict operations.

All functions must be called on the STA thread via dispatch().
"""

from __future__ import annotations

import os
import logging
import tempfile
from typing import Any
from xml.etree import ElementTree as ET

from configurationdesk_com_bridge.domains.verify_com import wait_for_state

_log = logging.getLogger(__name__)


def create_working_view(connection, name: str) -> dict[str, Any]:
    """Create a new working view for organizing signal chains."""
    before = list_working_views(connection)
    wv = connection.active.WorkingViews
    wv.Add("", name)
    verified, views_after = wait_for_state(
        lambda: list_working_views(connection),
        lambda names: name in names,
    )
    return {
        "name": name,
        "working_views": views_after,
        "verified": verified and name not in before or name in views_after,
    }


def list_working_views(connection) -> list[str]:
    """List all working views in the project."""
    wv = connection.active.WorkingViews
    views = []

    # Try Python COM iteration first (most reliable)
    try:
        for item in wv:
            try:
                views.append(item.Name)
            except Exception:
                pass
        return views
    except (TypeError, AttributeError):
        pass

    # Try 1-based indexing with explicit int conversion
    try:
        count = int(wv.Count)
        for i in range(1, count + 1):
            try:
                views.append(wv.Item(i).Name)
            except Exception:
                pass
        return views
    except Exception:
        pass

    # Try 0-based indexing
    try:
        count = int(wv.Count)
        for i in range(count):
            try:
                views.append(wv.Item(i).Name)
            except Exception:
                pass
        return views
    except Exception:
        pass

    return views


def remove_working_view(connection, name: str) -> dict[str, Any]:
    """Remove a working view by name."""
    wv = connection.active.WorkingViews
    for i in range(1, wv.Count + 1):
        if wv.Item(i).Name == name:
            wv.Remove(wv.Item(i))
            return {"name": name, "removed": True}
    return {"error": True, "detail": f"Working view '{name}' not found"}


def clear_all_working_views(connection) -> dict[str, Any]:
    """Remove all working views from the project."""
    connection.active.WorkingViews.Clear()
    try:
        count = connection.active.WorkingViews.Count
    except Exception:
        count = 0
    return {"remaining": count, "verified": count == 0}


def export_working_view(connection, name: str, path: str) -> dict[str, Any]:
    """Export a working view's signal chain to a file."""
    abs_path = os.path.abspath(path)
    wv = connection.active.WorkingViews
    for i in range(1, wv.Count + 1):
        if wv.Item(i).Name == name:
            wv.Item(i).Export(abs_path)
            verified = os.path.isfile(abs_path)
            return {"name": name, "path": abs_path, "verified": verified}
    return {"error": True, "detail": f"Working view '{name}' not found"}


def check_conflicts(connection) -> dict[str, Any]:
    """Export and parse all configuration conflicts."""
    conflicts_path = os.path.join(tempfile.mkdtemp(), "conflicts.xml")
    connection.algorithms.ExportConflictsToXML(conflicts_path, [], "")
    tree = ET.parse(conflicts_path)  # noqa: S314 - trusted local file
    conflicts = []
    for item in tree.findall(".//Item"):
        columns = {
            col.attrib.get("Name", ""): col.attrib.get("Value", "")
            for col in item.findall("Column")
        }
        if columns.get("Name"):
            conflicts.append(
                {
                    "name": columns.get("Name", ""),
                    "context": columns.get("Context", ""),
                    "property": columns.get("Property", ""),
                    "value": columns.get("Value", ""),
                    "suggested_values": columns.get("Suggested Values", ""),
                    "effect": columns.get("Effect", ""),
                }
            )
    return {"conflicts": conflicts, "count": len(conflicts)}
