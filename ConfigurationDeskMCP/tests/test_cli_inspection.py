"""CLI inspection tests that do not require ConfigurationDesk to start."""

from __future__ import annotations

import pytest

from sources import main
from tests._mcp_inventory import expected_inventory

pytest.importorskip("mcp")


@pytest.mark.parametrize(
    ("argument", "inventory_key"),
    [
        ("--list-tools", "tools"),
        ("--list-resources", "resources"),
        ("--list-prompts", "prompts"),
    ],
)
def test_inspection_command_matches_reviewed_inventory(argument, inventory_key, capsys):
    main.main([argument])

    assert tuple(capsys.readouterr().out.splitlines()) == expected_inventory()[inventory_key]
