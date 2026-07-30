# -*- coding: utf-8 -*-
"""Fixtures and helpers shared by the per-domain tool tests."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from tests import _fake_bridge


@pytest.fixture
def fake_bridge(monkeypatch):
    """Patch the bridge boundary in every service module with an in-memory fake."""
    return _fake_bridge.install(monkeypatch)


def run_ok(coro) -> dict[str, Any]:
    """Run a service coroutine, assert a success envelope, and return the payload."""
    payload = json.loads(asyncio.run(coro))
    assert payload.get("success") is True, payload
    return payload


def run_raw(coro) -> dict[str, Any]:
    """Run a service coroutine and return the decoded payload without asserting."""
    return json.loads(asyncio.run(coro))
