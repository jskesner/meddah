"""Shared pytest fixtures, including mandatory Zero-AI enforcement (Golden Rule #2)."""

from __future__ import annotations

import os
import socket

import pytest


@pytest.fixture(autouse=True)
def _enforce_zero_ai_environment(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Block AI providers and external LLM sockets when running @pytest.mark.zero_ai tests."""
    if request.node.get_closest_marker("zero_ai") is None:
        return

    monkeypatch.setenv("AI_PROVIDER", "none")
    monkeypatch.setenv("OLLAMA_BASE_URL", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("GEMINI_API_KEY", "")

    def _blocked_create_connection(
        address: tuple[str, int],
        *args: object,
        **kwargs: object,
    ) -> socket.socket:
        raise RuntimeError(
            f"Outbound network connection to {address!r} blocked during zero_ai test run."
        )

    if os.environ.get("ALLOW_ZERO_AI_LOOPBACK") != "1":
        monkeypatch.setattr(socket, "create_connection", _blocked_create_connection)
