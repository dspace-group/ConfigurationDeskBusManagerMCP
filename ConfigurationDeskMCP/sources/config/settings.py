"""Server configuration — read from environment variables or .env file."""

from __future__ import annotations

from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version as _pkg_version
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _resolve_server_version() -> str:
    """Return the installed package version, or a local fallback."""
    for dist in ("configurationdesk-mcp-server", "configurationdesk_mcp_server"):
        try:
            return _pkg_version(dist)
        except PackageNotFoundError:
            continue
    return "0.0.0+local"


class Settings(BaseSettings):
    """Typed, env-var-backed configuration. .env loaded automatically if present."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Transport ─────────────────────────────────────────────────────────────

    mcp_transport: Literal["stdio", "streamable-http"] = Field(
        default="stdio",
        description="MCP transport to use. Stdio is the supported public transport; "
        "streamable HTTP is an explicit loopback-only opt-in.",
    )
    mcp_enable_streamable_http: bool = Field(
        default=False,
        description="Allow the experimental loopback-only streamable HTTP transport. "
        "Remote HTTP deployment is not supported.",
    )
    mcp_host: str = Field(
        default="127.0.0.1",
        description="Bind host for the HTTP transport. Ignored for stdio.",
    )
    mcp_port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="TCP port for the HTTP transport. Ignored for stdio.",
    )

    # ── Logging ───────────────────────────────────────────────────────────────

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Python logging level for all server-side (stderr) output.",
    )

    # ── COM bridge ────────────────────────────────────────────────────────────

    com_timeout_ms: int = Field(
        default=30000,
        ge=500,
        le=120_000,
        description="Wall-clock timeout (ms) for any single COM method call. "
        "Calls that exceed this budget raise BridgeTimeoutError. "
        "The default stays above the internal verification observe window used by mutating COM operations.",
    )
    com_launch_timeout_ms: int = Field(
        default=30_000,
        ge=5_000,
        le=120_000,
        description="Max ms to wait for ConfigurationDesk to finish initializing after launch.",
    )
    com_reconnect_attempts: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum number of reconnection attempts after "
        "RPC_E_DISCONNECTED before the circuit opens.",
    )

    # ── Server identity ───────────────────────────────────────────────────────

    server_version: str = Field(
        default_factory=_resolve_server_version,
        description="Semantic version reported in the MCP initialize response. "
        "Resolved from installed package metadata when available.",
    )

    # ── Validators ────────────────────────────────────────────────────────────

    @field_validator("mcp_host")
    @classmethod
    def _host_not_empty(cls, value: str) -> str:
        if not value.strip():
            msg = "mcp_host must not be empty"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _streamable_http_is_loopback_only(self) -> Settings:
        if self.mcp_transport != "streamable-http":
            return self
        if not self.mcp_enable_streamable_http:
            msg = (
                "streamable-http is disabled by default. Set "
                "MCP_ENABLE_STREAMABLE_HTTP=true to enable loopback-only HTTP."
            )
            raise ValueError(msg)
        if self.mcp_host.strip().lower() not in {"127.0.0.1", "::1", "localhost"}:
            msg = "streamable-http must bind to a loopback host in this release."
            raise ValueError(msg)
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached Settings instance.

    In tests, call get_settings.cache_clear() after changing env vars.
    """
    return Settings()
