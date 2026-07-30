"""COM bridge exception hierarchy.

All exceptions raised inside the com_bridge package are subclasses of BridgeError.
"""

from __future__ import annotations


class BridgeError(Exception):
    """Base class for all COM bridge errors."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "BRIDGE_ERROR",
        retryable: bool = False,
        recovery_hint: str = "",
        hresult: int | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.retryable = retryable
        self.recovery_hint = recovery_hint
        self.hresult = hresult


class BridgeConnectionError(BridgeError):
    """ConfigurationDesk is not running or the COM connection is lost."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "COM_DISCONNECTED",
        retryable: bool = True,
        recovery_hint: str = "Ensure ConfigurationDesk is running, then retry.",
        hresult: int | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code=error_code,
            retryable=retryable,
            recovery_hint=recovery_hint,
            hresult=hresult,
        )


class BridgeTimeoutError(BridgeError):
    """A COM method call exceeded the configured timeout."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "COM_TIMEOUT",
        retryable: bool = True,
        recovery_hint: str = "Retry after a short delay.",
        hresult: int | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code=error_code,
            retryable=retryable,
            recovery_hint=recovery_hint,
            hresult=hresult,
        )


class BridgeNotInstalledError(BridgeError):
    """ConfigurationDesk is not installed on this machine."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "BRIDGE_NOT_INSTALLED",
        retryable: bool = False,
        recovery_hint: str = "Install ConfigurationDesk and ensure pywin32 is available.",
        hresult: int | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code=error_code,
            retryable=retryable,
            recovery_hint=recovery_hint,
            hresult=hresult,
        )


class BridgeOperationError(BridgeError):
    """A COM operation failed for a domain-specific reason."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "BRIDGE_OPERATION_ERROR",
        retryable: bool = False,
        recovery_hint: str = "",
        hresult: int | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code=error_code,
            retryable=retryable,
            recovery_hint=recovery_hint,
            hresult=hresult,
        )


class BridgeUiBlockedError(BridgeError):
    """COM call rejected because ConfigurationDesk is showing a modal dialog."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "COM_UI_BLOCKING",
        retryable: bool = True,
        recovery_hint: str = "Dismiss the open ConfigurationDesk dialog, then retry.",
        hresult: int | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code=error_code,
            retryable=retryable,
            recovery_hint=recovery_hint,
            hresult=hresult,
        )


class BridgePreconditionError(BridgeError):
    """A required domain-state precondition was not met before the COM call."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "BRIDGE_PRECONDITION",
        retryable: bool = False,
        recovery_hint: str = "",
        hresult: int | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code=error_code,
            retryable=retryable,
            recovery_hint=recovery_hint,
            hresult=hresult,
        )


class BridgeCircuitOpenError(BridgeError):
    """Too many reconnection failures — circuit is open."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "BRIDGE_CIRCUIT_OPEN",
        retryable: bool = False,
        recovery_hint: str = "Restart ConfigurationDesk and the MCP server.",
        hresult: int | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code=error_code,
            retryable=retryable,
            recovery_hint=recovery_hint,
            hresult=hresult,
        )
