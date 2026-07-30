"""Shared response helpers for all tools.

Every tool returns a JSON string via one of these helpers.
"""

from __future__ import annotations

import json
from typing import Any


def success_response(**kwargs: Any) -> str:
    """Create a JSON-formatted success response string.

    When verification has been performed, callers should include
    ``verified=True`` so consumers know the state was confirmed.
    """
    return json.dumps({"success": True, **kwargs}, indent=2, default=str)


def unverified_response(**kwargs: Any) -> str:
    """Create a JSON-formatted response for operations that cannot be verified.

    The COM call completed without error, but there is no reliable way to
    confirm the requested state change actually occurred.
    """
    return json.dumps({"success": True, "verified": False, **kwargs}, indent=2, default=str)


def error_response(
    message: str,
    transient: bool = False,
    *,
    error_code: str = "BRIDGE_UNKNOWN",
    recovery_hint: str = "",
    next_action: str = "",
    retryable: bool | None = None,
) -> str:
    """Create a JSON-formatted error response string.

    Args:
        message: Human-readable error description.
        transient: True if the error may resolve on retry.
        error_code: Machine-readable error code for generic failures.
        recovery_hint: Actionable guidance for the user or model.
        next_action: Concrete guidance for what tool to call next.
            If empty, a default is provided based on transient flag.
        retryable: Explicit retryable flag. If None, derived from transient.
    """
    if retryable is None:
        retryable = transient

    if not recovery_hint:
        if transient:
            recovery_hint = (
                "The failure may be transient. Retry once after a short delay. "
                "If it repeats, inspect the current ConfigurationDesk state."
            )
        else:
            recovery_hint = (
                "Inspect the error message and current ConfigurationDesk state "
                "before trying a different operation."
            )

    if not next_action:
        if transient:
            next_action = "Retry this call once. If it fails again, call `get_application_status` to check prerequisites."
        else:
            next_action = "Do NOT retry this call. Read the error message to understand what went wrong and try a different approach or fix the input parameters."

    return json.dumps(
        {
            "success": False,
            "error": message,
            "error_code": error_code,
            "retryable": retryable,
            "recovery_hint": recovery_hint,
            "next_action": next_action,
        },
        indent=2,
        default=str,
    )
