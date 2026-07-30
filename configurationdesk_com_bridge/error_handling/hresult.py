"""HRESULT classification for ConfigurationDesk COM errors.

Maps Windows HRESULT codes to BridgeError subclasses.
"""

from __future__ import annotations

import logging

from configurationdesk_com_bridge.errors import (
    BridgeConnectionError,
    BridgeError,
    BridgeOperationError,
    BridgeUiBlockedError,
)

_log = logging.getLogger(__name__)

# HRESULT → (error_code, BridgeError subclass, retryable, recovery_hint)
_HRESULT_MAP: dict[int, tuple[str, type[BridgeError], bool, str]] = {
    # UI blocking — STA is busy with a modal dialog
    0x80010001: (
        "COM_UI_BLOCKING",
        BridgeUiBlockedError,
        True,
        "Dismiss the open ConfigurationDesk dialog, then retry.",
    ),
    # RPC_E_DISCONNECTED — COM server went away
    0x80010108: (
        "COM_DISCONNECTED",
        BridgeConnectionError,
        True,
        "Call `start_configurationdesk` to re-establish the connection.",
    ),
    # CO_E_OBJNOTCONNECTED — COM object disconnected from server
    0x80010100: (
        "COM_DISCONNECTED",
        BridgeConnectionError,
        True,
        "Call `start_configurationdesk` to re-establish the connection.",
    ),
    # RPC_E_SERVER_DIED — server crashed mid-call
    0x80010007: (
        "COM_DISCONNECTED",
        BridgeConnectionError,
        True,
        "ConfigurationDesk process crashed. Call `start_configurationdesk` to restart.",
    ),
    # RPC_E_SERVER_DIED_DNE — server died, did not execute
    0x80010012: (
        "COM_DISCONNECTED",
        BridgeConnectionError,
        True,
        "ConfigurationDesk process crashed. Call `start_configurationdesk` to restart.",
    ),
    # DISP_E_MEMBERNOTFOUND — COM property/method not found (stale proxy or missing prerequisite)
    0x80020003: (
        "COM_MEMBER_NOT_FOUND",
        BridgeOperationError,
        False,
        "A required COM object is not accessible. Ensure the prerequisite step was completed "
        "(e.g., create_project before add_application). Call `get_application_status` to check state.",
    ),
    # RPC_E_SERVER_UNAVAILABLE — COM server not running
    0x800706BA: (
        "COM_SERVER_UNAVAILABLE",
        BridgeConnectionError,
        True,
        "Call `start_configurationdesk` to start ConfigurationDesk.",
    ),
    # CO_E_SERVER_EXEC_FAILURE — server launch failed
    0x80080005: (
        "COM_SERVER_EXEC_FAILURE",
        BridgeConnectionError,
        True,
        "ConfigurationDesk could not be started. Check installation.",
    ),
}

# Facility-based fallback (HRESULT bits 16-26)
_FACILITY_RPC = 0x07


def classify_com_error(exc: Exception) -> BridgeError:
    """Convert a raw COM exception into a typed BridgeError subclass.

    Handles pywintypes.com_error and generic exceptions.
    """
    hresult = _extract_hresult(exc)
    if hresult is not None:
        unsigned = hresult & 0xFFFFFFFF
        entry = _HRESULT_MAP.get(unsigned)
        if entry:
            code, cls, retryable, hint = entry
            return cls(
                str(exc),
                error_code=code,
                retryable=retryable,
                recovery_hint=hint,
                hresult=unsigned,
            )

        # Facility-based fallback
        facility = (unsigned >> 16) & 0x7FF
        if facility == _FACILITY_RPC:
            return BridgeConnectionError(
                str(exc),
                error_code="COM_RPC_ERROR",
                retryable=True,
                recovery_hint="Check ConfigurationDesk connection.",
                hresult=unsigned,
            )

        return BridgeOperationError(
            str(exc),
            error_code="BRIDGE_UNKNOWN",
            retryable=False,
            recovery_hint="",
            hresult=unsigned,
        )

    return BridgeOperationError(
        str(exc),
        error_code="BRIDGE_UNKNOWN",
        retryable=False,
    )


def _extract_hresult(exc: Exception) -> int | None:
    """Extract HRESULT integer from a pywintypes.com_error or similar."""
    if hasattr(exc, "hresult"):
        return exc.hresult
    if exc.args and isinstance(exc.args[0], int):
        return exc.args[0]
    return None
