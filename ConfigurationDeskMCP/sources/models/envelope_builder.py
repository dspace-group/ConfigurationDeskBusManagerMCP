"""Envelope builder — converts a BridgeError into a structured MCP error response."""

from __future__ import annotations

import json

from configurationdesk_com_bridge.errors import (
    BridgeCircuitOpenError,
    BridgeConnectionError,
    BridgeError,
    BridgeOperationError,
    BridgePreconditionError,
    BridgeTimeoutError,
    BridgeUiBlockedError,
)
from sources.models.errors import ErrorEnvelope

_CATEGORY_MAP: dict[type[BridgeError], str] = {
    BridgeConnectionError: "CONNECTION",
    BridgeUiBlockedError: "UI_BLOCKING",
    BridgeCircuitOpenError: "CIRCUIT",
    BridgePreconditionError: "PRECONDITION",
    BridgeTimeoutError: "TIMEOUT",
    BridgeOperationError: "OPERATION",
}

_CODE_CATEGORY_MAP: dict[str, str] = {
    "BRIDGE_UNKNOWN": "UNKNOWN",
}

# Concrete next-action guidance per error category — tells the model exactly what to do.
_NEXT_ACTION_MAP: dict[str, str] = {
    "CONNECTION": "Call `start_configurationdesk` to establish the COM connection. If that also fails, call `diagnose_connection` to get detailed diagnostics.",
    "UI_BLOCKING": "A dialog is open in ConfigurationDesk blocking automation. Ask the user to dismiss it, then retry the same call.",
    "CIRCUIT": "The COM connection is broken beyond repair. Call `stop_configurationdesk` then `start_configurationdesk` to restart fresh.",
    "PRECONDITION": "A prerequisite is not met. Call `get_application_status` to check what is missing (project, application, or connection).",
    "TIMEOUT": "The operation timed out. Retry this same call once. If it times out again, the operation may be too heavy — try breaking it into smaller steps.",
    "OPERATION": "This operation failed permanently. Do NOT retry. Read the error message to understand what went wrong and try a different approach.",
    "UNKNOWN": "An unexpected error occurred. Call `get_application_status` to check the current state before proceeding.",
    "SYSTEM": "A system-level error occurred. Call `diagnose_connection` to check the environment.",
}


def _resolve_category(exc: BridgeError) -> str:
    if exc.error_code in _CODE_CATEGORY_MAP:
        return _CODE_CATEGORY_MAP[exc.error_code]
    category = _CATEGORY_MAP.get(type(exc))
    if category:
        return category
    for cls in type(exc).__mro__:
        if cls in _CATEGORY_MAP:
            return _CATEGORY_MAP[cls]
    return "UNKNOWN"


def build_envelope(
    exc: BridgeError,
    *,
    correlation_id: str = "",
) -> ErrorEnvelope:
    """Build an ErrorEnvelope from a BridgeError."""
    category = _resolve_category(exc)
    detail = ""
    if exc.hresult is not None:
        detail = f"HRESULT=0x{exc.hresult:08X}"

    return ErrorEnvelope(
        error_code=exc.error_code,
        category=category,  # type: ignore[arg-type]
        message=str(exc),
        detail=detail,
        hresult=exc.hresult,
        retryable=exc.retryable,
        recovery_hint=exc.recovery_hint,
        correlation_id=correlation_id,
    )


def tool_error_result(
    exc: BridgeError,
    *,
    correlation_id: str = "",
) -> str:
    """Return a JSON-serialised error payload suitable for returning from an MCP tool."""
    if not correlation_id:
        from configurationdesk_com_bridge import get_correlation_id  # noqa: PLC0415

        correlation_id = get_correlation_id()
    envelope = build_envelope(exc, correlation_id=correlation_id)
    payload = envelope.model_dump()
    payload["markdown"] = envelope.to_markdown()
    payload["success"] = False
    # Add next_action — concrete guidance so cheaper models know what tool to call next
    category = envelope.category
    payload["next_action"] = _NEXT_ACTION_MAP.get(category, _NEXT_ACTION_MAP["UNKNOWN"])
    return json.dumps(payload, indent=2, default=str)
