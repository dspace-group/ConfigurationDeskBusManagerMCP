# -*- coding: utf-8 -*-
"""Smoke tests for the ConfigurationDesk MCP server."""

import json

import pytest

from sources.config.settings import Settings, get_settings
from configurationdesk_com_bridge.errors import BridgeError, BridgeConnectionError
from sources.models.errors import ErrorEnvelope
from sources.models.envelope_builder import build_envelope
from sources.tools._responses import success_response, error_response, unverified_response


class TestSettings:
    def test_defaults(self):
        s = Settings()
        assert s.mcp_transport == "stdio"
        assert s.com_timeout_ms == 30000

    def test_get_settings_cached(self):
        a = get_settings()
        b = get_settings()
        assert a is b

    def test_streamable_http_requires_explicit_opt_in(self):
        with pytest.raises(ValueError, match="MCP_ENABLE_STREAMABLE_HTTP"):
            Settings(mcp_transport="streamable-http")

    def test_streamable_http_requires_loopback_host(self):
        with pytest.raises(ValueError, match="loopback"):
            Settings(
                mcp_transport="streamable-http",
                mcp_enable_streamable_http=True,
                mcp_host="0.0.0.0",
            )

    def test_streamable_http_allows_explicit_loopback_opt_in(self):
        settings = Settings(
            mcp_transport="streamable-http",
            mcp_enable_streamable_http=True,
            mcp_host="127.0.0.1",
        )

        assert settings.mcp_enable_streamable_http is True


class TestBridgeErrors:
    def test_hierarchy(self):
        err = BridgeConnectionError("fail")
        assert isinstance(err, BridgeError)
        assert err.error_code == "COM_DISCONNECTED"
        assert err.retryable is True

    def test_envelope_from_error(self):
        err = BridgeConnectionError("no COM", recovery_hint="restart")
        env = build_envelope(err)
        assert isinstance(env, ErrorEnvelope)
        assert env.retryable is True
        assert "restart" in env.recovery_hint
        md = env.to_markdown()
        assert "COM_DISCONNECTED" in md


class TestResponseHelpers:
    def test_success(self):
        data = json.loads(success_response(message="done", count=3))
        assert data["success"] is True
        assert data["count"] == 3

    def test_error(self):
        data = json.loads(error_response("bad"))
        assert data["success"] is False
        assert data["retryable"] is False

    def test_unverified(self):
        data = json.loads(unverified_response(message="ok"))
        assert data["verified"] is False


class TestServerImport:
    def test_mcp_instance(self):
        from sources.server.app import mcp

        assert mcp.name == "ConfigurationDesk MCP Server"

    def test_tool_count(self):
        import sources.server.app  # noqa: F401
        import sources.server.registry  # noqa: F401
        from sources.server.app import mcp

        tools = list(mcp._tool_manager._tools.keys())
        assert len(tools) >= 75
