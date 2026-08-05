"""Bounded exponential reconnect scheduling."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ReconnectBackoff:
    """Track silent reconnect delays with an upper bound."""

    initial: float = 2.0
    maximum: float = 60.0
    attempts: int = 0

    def next_delay(self) -> float:
        """Return the next delay and advance the attempt count."""
        delay = min(self.maximum, self.initial * (2**self.attempts))
        self.attempts += 1
        return delay

    def reset(self) -> None:
        """Reset after a successful navigation or connection."""
        self.attempts = 0
