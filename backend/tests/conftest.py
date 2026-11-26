"""Shared pytest fixtures, including mandatory Zero-AI enforcement (Golden Rule #2)."""

from __future__ import annotations

import os
import socket
from collections.abc import Callable
from typing import Any

import pytest


@pytest.fixture
def _allowed_loopback_ports() -> set[int]:
    return set()


@pytest.fixture
def allow_loopback_port(_allowed_loopback_ports: set[int]) -> Callable[[int], None]:
    """Allow local test client connections to a specific ephemeral loopback daemon port."""

    def _allow(port: int) -> None:
        if port <= 0 or port == 11434:
            raise ValueError(f"Refusing to whitelist loopback port {port}")
        _allowed_loopback_ports.add(port)

    return _allow


@pytest.fixture(autouse=True)
def _enforce_zero_ai_environment(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    _allowed_loopback_ports: set[int],
) -> None:
    """Block AI providers and external LLM sockets when running @pytest.mark.zero_ai tests."""
    if request.node.get_closest_marker("zero_ai") is None:
        return

    monkeypatch.setenv("AI_PROVIDER", "none")
    monkeypatch.setenv("OLLAMA_BASE_URL", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("GEMINI_API_KEY", "")

    real_create_connection: Any = socket.create_connection

    def _guarded_create_connection(
        address: tuple[str, int],
        *args: Any,
        **kwargs: Any,
    ) -> socket.socket:
        host, port = address[0], int(address[1])
        if (
            host in {"127.0.0.1", "::1", "localhost"}
            and port in _allowed_loopback_ports
            and port != 11434
        ):
            return real_create_connection(address, *args, **kwargs)
        raise RuntimeError(
            f"Outbound network connection to {address!r} blocked during zero_ai test run."
        )

    if os.environ.get("ALLOW_ZERO_AI_LOOPBACK") != "1":
        monkeypatch.setattr(socket, "create_connection", _guarded_create_connection)
