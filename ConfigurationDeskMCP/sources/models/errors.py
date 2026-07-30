"""ErrorEnvelope — structured error payload for all failed tool calls."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ErrorEnvelope(BaseModel):
    """Structured error payload for failed tool calls."""

    error_code: str = Field(
        description="Machine-readable error code, e.g. 'COM_DISCONNECTED'.",
    )
    category: Literal[
        "CONNECTION",
        "UI_BLOCKING",
        "CIRCUIT",
        "PRECONDITION",
        "OPERATION",
        "TIMEOUT",
        "SYSTEM",
        "UNKNOWN",
    ] = Field(
        description="High-level error category.",
    )
    message: str = Field(
        description="Human-readable description of what went wrong.",
    )
    detail: str = Field(
        default="",
        description="Technical detail such as the raw HRESULT value.",
    )
    hresult: int | None = Field(
        default=None,
        description="Raw unsigned HRESULT integer. None when not COM-originated.",
    )
    retryable: bool = Field(
        description="True when the LLM may retry the same tool call after a short delay.",
    )
    recovery_hint: str = Field(
        default="",
        description="Actionable guidance for the LLM or user.",
    )
    correlation_id: str = Field(
        default="",
        description="UUID linking this error to a log entry.",
    )

    def to_markdown(self) -> str:
        lines = [
            "## ConfigurationDesk MCP Error",
            "",
            f"**Code:** `{self.error_code}`  ",
            f"**Category:** {self.category}  ",
            f"**Retryable:** {'Yes' if self.retryable else 'No'}  ",
            "",
            f"**Message:** {self.message}",
        ]
        if self.detail:
            lines += ["", f"**Detail:** `{self.detail}`"]
        if self.hresult is not None:
            lines += [f"**HRESULT:** `0x{self.hresult:08X}`"]
        if self.recovery_hint:
            lines += ["", f"**Recovery:** {self.recovery_hint}"]
        if self.correlation_id:
            lines += ["", f"**Correlation ID:** `{self.correlation_id}`"]
        return "\n".join(lines)
