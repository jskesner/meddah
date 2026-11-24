"""Deterministic named RNG streams using a SHA-256 counter-mode DRBG."""

from __future__ import annotations

import hashlib
import struct
from collections.abc import Sequence
from typing import TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")

_UINT64_MOD = 1 << 64


class RngStreamState(BaseModel):
    """Serializable checkpoint of a named deterministic RNG stream."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    seed: str = Field(min_length=1, description="Base campaign or scene RNG seed.")
    stream_name: str = Field(min_length=1, description="Logical RNG stream identifier.")
    position: int = Field(default=0, ge=0, description="Number of 64-bit draws already consumed.")


class DeterministicRngStream:
    """Platform-independent counter-mode PRNG backed by SHA-256."""

    def __init__(self, seed: str, stream_name: str, position: int = 0) -> None:
        if not seed:
            raise ValueError("RNG seed must be non-empty.")
        if not stream_name:
            raise ValueError("RNG stream_name must be non-empty.")
        if position < 0:
            raise ValueError("RNG position must be non-negative.")
        self._seed = seed
        self._stream_name = stream_name
        self._position = position

    @property
    def seed(self) -> str:
        """Return base seed string."""
        return self._seed

    @property
    def stream_name(self) -> str:
        """Return stream identifier."""
        return self._stream_name

    @property
    def position(self) -> int:
        """Return current counter position."""
        return self._position

    def next_u64(self) -> int:
        """Draw the next deterministic unsigned 64-bit integer and advance counter."""
        payload = f"{self._seed}:{self._stream_name}:{self._position}".encode()
        digest = hashlib.sha256(payload).digest()
        self._position += 1
        val: int = struct.unpack(">Q", digest[:8])[0]
        return val

    def randint(self, low: int, high: int) -> int:
        """Return an integer N such that low <= N <= high using unbiased rejection sampling."""
        if low > high:
            raise ValueError(f"Invalid randint bounds: low={low} > high={high}")
        span = high - low + 1
        if span == 1:
            self.next_u64()
            return low
        limit = _UINT64_MOD - (_UINT64_MOD % span)
        while True:
            sample = self.next_u64()
            if sample < limit:
                return low + (sample % span)

    def choice(self, items: Sequence[T]) -> T:
        """Select a deterministic element from a non-empty sequence."""
        if not items:
            raise ValueError("Cannot choose from an empty sequence.")
        idx = self.randint(0, len(items) - 1)
        return items[idx]

    def shuffle(self, items: Sequence[T]) -> list[T]:
        """Return a deterministically shuffled copy of items using Fisher-Yates."""
        result = list(items)
        for idx in range(len(result) - 1, 0, -1):
            swap_idx = self.randint(0, idx)
            result[idx], result[swap_idx] = result[swap_idx], result[idx]
        return result

    def snapshot(self) -> RngStreamState:
        """Return immutable checkpoint state for event recording and replay."""
        return RngStreamState(
            seed=self._seed,
            stream_name=self._stream_name,
            position=self._position,
        )


class SceneRngRegistry:
    """Collection of isolated named RNG streams scoped to a scene or simulation run."""

    def __init__(
        self,
        scene_seed: str,
        initial_states: dict[str, RngStreamState] | None = None,
    ) -> None:
        if not scene_seed:
            raise ValueError("scene_seed must be non-empty.")
        self._scene_seed = scene_seed
        self._streams: dict[str, DeterministicRngStream] = {}
        if initial_states:
            for name in sorted(initial_states):
                state = initial_states[name]
                self._streams[name] = DeterministicRngStream(
                    seed=state.seed,
                    stream_name=state.stream_name,
                    position=state.position,
                )

    @property
    def scene_seed(self) -> str:
        """Return root seed for the registry."""
        return self._scene_seed

    def stream(self, name: str) -> DeterministicRngStream:
        """Get or initialize the named RNG stream."""
        existing = self._streams.get(name)
        if existing is None:
            existing = DeterministicRngStream(seed=self._scene_seed, stream_name=name, position=0)
            self._streams[name] = existing
        return existing

    def snapshots(self) -> dict[str, RngStreamState]:
        """Export deterministic sorted stream states."""
        return {name: self._streams[name].snapshot() for name in sorted(self._streams)}
