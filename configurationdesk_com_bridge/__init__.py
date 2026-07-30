# SPDX-License-Identifier: Apache-2.0
# Copyright (c) dSPACE Group SE & Co. KG.
"""ConfigurationDesk COM Bridge — open-source COM automation library (SDK).

Public API (the ONLY symbols code outside this package may import):

    from configurationdesk_com_bridge import (
        startup,
        shutdown,
        dispatch,
        ensure_connected,
        get_connection,
        new_correlation_id,
        get_correlation_id,
        set_correlation_id,
    )
    from configurationdesk_com_bridge.errors import BridgeError, ...
    from configurationdesk_com_bridge.domains import bus_config_com, ...
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextvars
import logging
import time
import uuid
from typing import Any, Callable

from configurationdesk_com_bridge import sta_thread as _sta
from configurationdesk_com_bridge.connection import (
    ConfigurationDeskConnection,
    ConnectionState,
)
from configurationdesk_com_bridge.errors import (
    BridgeConnectionError,
    BridgeError,
    BridgeTimeoutError,
)

__all__ = [
    "startup",
    "shutdown",
    "dispatch",
    "get_connection",
    "ensure_connected",
    "new_correlation_id",
    "get_correlation_id",
    "set_correlation_id",
]

_log = logging.getLogger(__name__)

_connection: ConfigurationDeskConnection | None = None
_default_timeout_ms = 30000

# Correlation id propagated across a logical tool invocation for observability.
_correlation_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "cd_correlation_id", default=""
)


def new_correlation_id() -> str:
    """Generate, set, and return a fresh correlation id for the current context."""
    cid = uuid.uuid4().hex
    _correlation_id.set(cid)
    return cid


def get_correlation_id() -> str:
    """Return the correlation id bound to the current context (may be empty)."""
    return _correlation_id.get()


def set_correlation_id(correlation_id: str) -> None:
    """Bind *correlation_id* to the current context."""
    _correlation_id.set(correlation_id)


def get_connection() -> ConfigurationDeskConnection:
    """Return the active connection. Raises if bridge is not started."""
    if _connection is None:
        msg = "COM bridge not started. Call startup() first."
        raise RuntimeError(msg)
    return _connection


async def startup(
    *,
    default_timeout_ms: int = 30000,
    launch_timeout_ms: int = 30000,
    reconnect_attempts: int = 3,
) -> None:
    """Start the STA thread only. Fast — completes in milliseconds.

    COM connection is deferred: ``ensure_connected()`` establishes it on the
    first ``start_configurationdesk`` tool call.
    """
    global _connection, _default_timeout_ms  # noqa: PLW0603
    _sta.startup()
    _default_timeout_ms = default_timeout_ms
    _connection = ConfigurationDeskConnection(
        launch_timeout_ms=launch_timeout_ms,
        reconnect_attempts=reconnect_attempts,
    )
    _log.debug("STA thread ready; COM connection deferred until first tool call")


async def ensure_connected(visible: bool = True) -> bool:
    """Guarantee the COM bridge is connected, (re)starting if necessary.

    Returns True if a new connection was established, False if already connected.
    """
    global _connection  # noqa: PLW0603
    if _connection is None:
        await startup()

    sta_thread = _sta.get_sta_thread()
    if _connection.state is ConnectionState.CONNECTED:
        health_future = sta_thread.submit(_connection.health_check)
        if await asyncio.wrap_future(health_future):
            return False
        future = sta_thread.submit(_connection.reconnect, visible)
    else:
        future = sta_thread.submit(_connection.connect, visible)

    await asyncio.wrap_future(future)
    health_future = sta_thread.submit(_connection.health_check)
    if not await asyncio.wrap_future(health_future):
        raise BridgeConnectionError(
            "ConfigurationDesk did not remain available after startup.",
            recovery_hint="Wait for ConfigurationDesk to finish starting, then call `start_configurationdesk` again.",
        )
    return True


async def shutdown() -> None:
    """Detach from ConfigurationDesk and stop the STA thread.

    This must be non-destructive: server shutdown should not close the user's
    ConfigurationDesk instance. Explicit shutdown remains available through the
    stop tool path that calls ``disconnect()``.
    """
    global _connection  # noqa: PLW0603
    if _connection is not None:
        try:
            future = _sta.get_sta_thread().submit(_connection.detach)
            await asyncio.wrap_future(future)
        except Exception as exc:  # noqa: BLE001
            _log.warning("COM detach error (ignored on shutdown): %s", exc)
        _connection = None
    _sta.shutdown()


def _guarded_call(fn: Callable[..., Any], args: tuple[Any, ...], reconnect: bool = True) -> Any:
    """Execute *fn* on the STA thread with a health-check/reconnect guard.

    If the COM connection is stale (ConfigurationDesk closed between calls),
    attempt a single reconnect before executing. This runs entirely on the
    STA thread so COM apartment rules are respected.
    """
    # The first arg is always the connection object for domain functions
    conn = args[0] if args else None
    if conn is not None and hasattr(conn, "health_check"):
        if not conn.health_check():
            if not reconnect:
                raise BridgeConnectionError(
                    "COM connection is not healthy.",
                    recovery_hint="Call `start_configurationdesk` to re-establish the connection.",
                )
            _log.warning("COM health check failed before dispatch — attempting reconnect")
            if conn.reconnect():
                _log.info("COM reconnect succeeded — proceeding with call")
            else:
                raise BridgeConnectionError(
                    "COM connection lost and reconnect failed.",
                    recovery_hint="Call `start_configurationdesk` to re-establish the connection.",
                )
    return fn(*args)


def _resolve_timeout_ms(timeout_ms: int | None) -> int:
    if timeout_ms is None:
        return _default_timeout_ms
    return timeout_ms


async def dispatch(
    fn: Callable[..., Any],
    *args: Any,
    timeout_ms: int | None = None,
    reconnect: bool = True,
) -> Any:
    """Submit *fn(*args)* to the STA thread and await the result.

    Includes an automatic health-check before execution. By default, a stale
    connection is reconnected once; pass ``reconnect=False`` for observational
    calls that must report a disconnected state without launching the product.

    Raises:
        BridgeTimeoutError: The call exceeded *timeout_ms*.
        BridgeError subclass: Any classified COM failure from *fn*.
        RuntimeError: Bridge not started or reconnect failed.
    """
    correlation_id = get_correlation_id() or new_correlation_id()
    operation = getattr(fn, "__name__", "unknown")
    effective_timeout_ms = _resolve_timeout_ms(timeout_ms)
    started = time.perf_counter()

    future: concurrent.futures.Future[Any] = _sta.get_sta_thread().submit(
        _guarded_call, fn, args, reconnect
    )
    timeout_s = effective_timeout_ms / 1000.0
    try:
        result = await asyncio.wait_for(asyncio.wrap_future(future), timeout=timeout_s)
    except TimeoutError as exc:
        future.cancel()
        _log.warning(
            "op=%s correlation_id=%s duration_ms=%.1f outcome=timeout",
            operation,
            correlation_id,
            (time.perf_counter() - started) * 1000.0,
        )
        raise BridgeTimeoutError(f"COM call timed out after {effective_timeout_ms} ms") from exc
    except BridgeError as exc:
        _log.warning(
            "op=%s correlation_id=%s duration_ms=%.1f outcome=error code=%s",
            operation,
            correlation_id,
            (time.perf_counter() - started) * 1000.0,
            exc.error_code,
        )
        raise
    _log.info(
        "op=%s correlation_id=%s duration_ms=%.1f outcome=ok",
        operation,
        correlation_id,
        (time.perf_counter() - started) * 1000.0,
    )
    return result
