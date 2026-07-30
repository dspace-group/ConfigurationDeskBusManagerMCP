"""Dispatch policy for bounded, non-mutating COM observations."""

from __future__ import annotations

from typing import Any, Callable

from configurationdesk_com_bridge import dispatch

OBSERVATION_TIMEOUT_MS = 5_000


async def dispatch_observation(fn: Callable[..., Any], *args: Any) -> Any:
    """Read COM state without reconnecting or launching ConfigurationDesk."""
    return await dispatch(
        fn,
        *args,
        timeout_ms=OBSERVATION_TIMEOUT_MS,
        reconnect=False,
    )
