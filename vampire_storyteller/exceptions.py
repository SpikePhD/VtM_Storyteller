from __future__ import annotations


class WorldStateError(Exception):
    """Base exception for deterministic world-state operations."""


class InvalidLocationError(WorldStateError):
    """Raised when a destination location does not exist."""


class MovementError(WorldStateError):
    """Raised when deterministic movement cannot be completed."""


class ContextBuildError(WorldStateError):
    """Raised when a scene snapshot cannot be built deterministically."""


class CommandParseError(WorldStateError):
    """Raised when structured command parsing fails."""
