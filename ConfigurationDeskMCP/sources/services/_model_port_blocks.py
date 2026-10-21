# -*- coding: utf-8 -*-
"""Shared policy for model port block names that are ambiguous across hierarchy levels."""

from __future__ import annotations

from sources.tools._responses import error_response


def ambiguous_model_port_block_response(detail: str, candidates: list[str]) -> str:
    """Refuse to guess between same-named model port blocks; the user must choose."""
    return error_response(
        detail,
        transient=False,
        error_code="AMBIGUOUS_TARGET",
        recovery_hint=(
            "Several model port blocks share this name at different hierarchy levels "
            "(e.g. one at the model root and one inside a subsystem). Choosing one "
            "silently could wire or expose the wrong block."
        ),
        next_action=(
            "Do NOT pick one yourself and do NOT retry with another guess. Ask the user "
            f"which model port block they mean, offering these candidates: {candidates}. "
            "Then retry with the chosen full hierarchy path as the model port block name."
        ),
    )
