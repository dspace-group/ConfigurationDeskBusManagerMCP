"""Read ConfigurationDesk conflicts as the Conflicts Viewer shows them.

Uses ``ICaAlgorithms.ExportConflictsToXML`` (ConfigurationDesk Automating Tool
Handling, ICaAlgorithms). The export keeps the Conflicts Viewer hierarchy
(context set > conflict > involved elements) and its display texts, which the
``ICaConflictManager`` API of ConfigurationDesk 2026-B does not provide
reliably. Must be called on the STA thread.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections import Counter
from typing import Any
from xml.etree import ElementTree as ET


def _item(element: ET.Element) -> dict[str, Any]:
    columns = {
        column.attrib.get("Name", ""): column.attrib.get("Value", "")
        for column in element.findall("Column")
    }
    return {
        "name": columns.get("Name", ""),
        "context": columns.get("Context", ""),
        "property": columns.get("Property", ""),
        "value": columns.get("Value", ""),
        "effect": columns.get("Effect", ""),
        "children": [_item(child) for child in element.findall("Item")],
    }


def export_conflict_tree(connection) -> list[dict[str, Any]]:
    """Return the context sets of the current conflicts, each with its conflict items."""
    directory = tempfile.mkdtemp()
    try:
        path = os.path.join(directory, "conflicts.xml")
        connection.algorithms.ExportConflictsToXML(path, [], "")
        root = ET.parse(path).getroot()  # noqa: S314 - file written by ConfigurationDesk
    finally:
        # A leftover temp file must not turn a completed operation into an error.
        shutil.rmtree(directory, ignore_errors=True)
    return [_item(element) for element in root.findall("Item")]


def _conflicts(tree: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"context_set": context_set["name"], **conflict}
        for context_set in tree
        for conflict in context_set["children"]
    ]


def new_conflicts(
    before: list[dict[str, Any]], after: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Return the conflicts in *after* that were not reported in *before*."""
    remaining = Counter(json.dumps(c, sort_keys=True) for c in _conflicts(before))
    added = []
    for conflict in _conflicts(after):
        key = json.dumps(conflict, sort_keys=True)
        if remaining[key]:
            remaining[key] -= 1
        else:
            added.append(conflict)
    return added
