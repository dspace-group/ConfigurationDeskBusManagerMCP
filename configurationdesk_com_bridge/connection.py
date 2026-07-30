"""ConfigurationDesk COM connection manager.

All methods run exclusively on the STA thread — no locks or per-thread
CoInitialize needed (the STA thread handles that).
"""

from __future__ import annotations

import enum
import logging
import os
import time

from configurationdesk_com_bridge.error_handling.hresult import classify_com_error
from configurationdesk_com_bridge.errors import (
    BridgeCircuitOpenError,
    BridgeError,
    BridgeNotInstalledError,
    BridgeTimeoutError,
)

_log = logging.getLogger(__name__)

try:
    import win32com.client

    COM_AVAILABLE = True
except ImportError:
    COM_AVAILABLE = False


class ConnectionState(enum.Enum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTED = "CONNECTED"
    RECONNECTING = "RECONNECTING"
    FAILED = "FAILED"


class ConfigurationDeskConnection:
    """COM connection for ConfigurationDesk.

    All public methods are called on the STA thread via ``dispatch()``.
    No internal locking is required.
    """

    # Default COM ProgID. Override per-deployment via CONFIGURATIONDESK_PROGID
    PRODUCT_ID = "ConfigurationDesk.Application"

    def __init__(
        self,
        *,
        launch_timeout_ms: int = 30000,
        reconnect_attempts: int = 3,
    ) -> None:
        self._app = None
        self._enums = None
        self._state = ConnectionState.DISCONNECTED
        self._launch_timeout_ms = launch_timeout_ms
        self._reconnect_attempts = max(1, reconnect_attempts)
        self._reconnect_failures = 0
        # Instance value shadows the class default; allows env-based override.
        self.PRODUCT_ID = os.environ.get("CONFIGURATIONDESK_PROGID", type(self).PRODUCT_ID)

    @property
    def state(self) -> ConnectionState:
        return self._state

    @property
    def is_connected(self) -> bool:
        return self._state is ConnectionState.CONNECTED

    def connect(self, visible: bool = True) -> bool:
        """Establish COM connection to ConfigurationDesk.

        Tries GetActiveObject first (attach), falls back to Dispatch (launch).
        If Dispatch fails with a type-library error (HRESULT 0x80029C4A),
        falls back to dynamic.Dispatch which bypasses the type library.
        """
        if not COM_AVAILABLE:
            raise BridgeNotInstalledError("COM libraries not available (pywin32 not installed)")
        try:
            self._acquire_application(reconnect=False)
            self._wait_until_ready()
            self._load_enums()
            self._set_visibility(visible)
            self._state = ConnectionState.CONNECTED
            self._reconnect_failures = 0
            return True
        except Exception as exc:
            self._state = ConnectionState.FAILED
            if isinstance(exc, BridgeError):
                raise
            raise classify_com_error(exc) from exc

    def disconnect(self, save: bool = True) -> bool:
        """Disconnect from ConfigurationDesk."""
        if self._app is None:
            self._state = ConnectionState.DISCONNECTED
            return True
        try:
            self._app.Quit(save)
            self._app = None
            self._state = ConnectionState.DISCONNECTED
            self._reconnect_failures = 0
            return True
        except Exception as exc:
            _log.warning("COM disconnect error: %s", exc)
            self._app = None
            self._state = ConnectionState.DISCONNECTED
            self._reconnect_failures = 0
            return False

    def detach(self) -> bool:
        """Detach bridge references without closing ConfigurationDesk.

        This is used by MCP/server process shutdown to avoid closing a user-owned
        ConfigurationDesk session when the bridge itself exits.
        """
        self._app = None
        self._enums = None
        self._state = ConnectionState.DISCONNECTED
        self._reconnect_failures = 0
        return True

    def health_check(self) -> bool:
        """Check whether the COM connection is still alive."""
        if self._app is None:
            return False
        try:
            _ = self._app.MainWindow.Visible
            return True
        except Exception:
            _log.warning("COM health check failed — connection may be broken")
            return False

    def reconnect(self, visible: bool = True) -> bool:
        """Attempt to re-establish the COM connection."""
        if not COM_AVAILABLE:
            raise BridgeNotInstalledError("COM libraries not available (pywin32 not installed)")
        if self._reconnect_failures >= self._reconnect_attempts:
            raise BridgeCircuitOpenError(
                f"COM reconnect failed {self._reconnect_failures} time(s); circuit open.",
                recovery_hint="Call `stop_configurationdesk` then `start_configurationdesk` to recover cleanly.",
            )
        self._state = ConnectionState.RECONNECTING
        try:
            self._app = None
            self._acquire_application(reconnect=True)
            self._wait_until_ready()
            self._load_enums()
            self._set_visibility(visible)
            self._state = ConnectionState.CONNECTED
            self._reconnect_failures = 0
            return True
        except Exception as exc:
            _log.error("Reconnection failed: %s", exc)
            self._state = ConnectionState.FAILED
            self._reconnect_failures += 1
            if self._reconnect_failures >= self._reconnect_attempts:
                raise BridgeCircuitOpenError(
                    f"COM reconnect failed {self._reconnect_failures} time(s); circuit open.",
                    recovery_hint="Call `stop_configurationdesk` then `start_configurationdesk` to recover cleanly.",
                    hresult=getattr(exc, "hresult", None),
                ) from exc
            if isinstance(exc, BridgeError):
                raise
            raise classify_com_error(exc) from exc

    # ── Convenience properties ────────────────────────────────────────────────

    @property
    def app(self):
        return self._app

    @property
    def enums(self):
        return self._enums

    @property
    def active(self):
        """Shortcut to ActiveApplication."""
        return self._app.ActiveApplication

    @property
    def components(self):
        return self._app.ActiveApplication.Components

    @property
    def relations(self):
        return self._app.ActiveApplication.Relations

    @property
    def algorithms(self):
        return self._app.ActiveApplication.Algorithms

    @property
    def busmanager(self):
        return self._app.ActiveApplication.Components.Item("BusManager")

    @property
    def model_topology(self):
        return self._app.ActiveApplication.Components.Item("ModelTopology")

    @property
    def hw_topology(self):
        return self._app.ActiveApplication.Components.Item("HardwareTopology")

    @property
    def build_management(self):
        return self._app.ActiveApplication.BuildManagement

    @property
    def platform_management(self):
        return self._app.PlatformManagement

    # ── Private helpers ───────────────────────────────────────────────────────

    def _acquire_application(self, *, reconnect: bool) -> None:
        try:
            self._app = win32com.client.GetActiveObject(self.PRODUCT_ID)
            if reconnect:
                _log.info("Reconnected to existing ConfigurationDesk instance")
            else:
                _log.info("Connected to existing ConfigurationDesk instance")
            return
        except Exception:
            pass

        try:
            self._app = win32com.client.Dispatch(self.PRODUCT_ID)
            if reconnect:
                _log.info("Started new ConfigurationDesk instance on reconnect")
            else:
                _log.info("Started new ConfigurationDesk instance")
            return
        except Exception as dispatch_exc:
            hresult = getattr(dispatch_exc, "hresult", None)
            exc_str = str(dispatch_exc)
            if (
                hresult == -0x7FFD63B6
                or "0x80029C4A" in exc_str
                or "type library" in exc_str.lower()
            ):
                _log.warning(
                    "Static Dispatch failed%s, falling back to dynamic.Dispatch",
                    " on reconnect" if reconnect else "",
                )
                from win32com.client.dynamic import Dispatch as _dyn_dispatch  # noqa: PLC0415

                self._app = _dyn_dispatch(self.PRODUCT_ID)
                if reconnect:
                    _log.info("Reconnected via dynamic.Dispatch")
                else:
                    _log.info("Started ConfigurationDesk via dynamic.Dispatch")
                return
            raise

    def _wait_until_ready(self) -> None:
        if self._app is None:
            raise BridgeNotInstalledError("ConfigurationDesk COM object is not available")

        deadline = time.monotonic() + (self._launch_timeout_ms / 1000.0)
        last_error: Exception | None = None

        while time.monotonic() < deadline:
            try:
                _ = self._app.MainWindow.Visible
                return
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                time.sleep(0.1)

        raise BridgeTimeoutError(
            f"ConfigurationDesk did not become ready within {self._launch_timeout_ms} ms",
            recovery_hint=(
                "Retry once or increase the COM launch timeout if startup is expected "
                "to take longer on this machine."
            ),
            hresult=getattr(last_error, "hresult", None),
        ) from last_error

    def _set_visibility(self, visible: bool) -> None:
        if not visible or self._app is None:
            return
        try:
            self._app.MainWindow.Visible = True
        except Exception:
            pass

    def _load_enums(self) -> None:
        """Load the optional dSPACE COM ``Enums`` helper if importable.

        Location may be provided via ``CONFIGURATIONDESK_COMMON_PATH``; otherwise
        the helper is imported from the normal Python path if already installed.
        No machine-specific path is hardcoded.
        """
        import sys  # noqa: PLC0415

        explicit = os.environ.get("CONFIGURATIONDESK_COMMON_PATH", "").strip()
        if explicit and os.path.isdir(explicit) and explicit not in sys.path:
            sys.path.insert(0, explicit)
        try:
            from dspace.com import Enums  # noqa: PLC0415

            self._enums = Enums(self._app)
        except Exception:  # noqa: BLE001
            _log.warning(
                "dSPACE COM Enums helper not importable; enum-typed operations may be "
                "unavailable. Set CONFIGURATIONDESK_COMMON_PATH to the dSPACECommon path."
            )
            self._enums = None
