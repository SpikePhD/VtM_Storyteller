from __future__ import annotations

from datetime import datetime, timedelta

from .world_state import WorldState


def parse_time(timestamp: str) -> datetime:
    return datetime.fromisoformat(timestamp)


def format_time(dt: datetime) -> str:
    return dt.isoformat()


def advance_time(world_state: WorldState, minutes: int) -> None:
    if minutes < 0:
        raise ValueError("minutes must be >= 0")

    current_dt = parse_time(world_state.current_time)
    updated_dt = current_dt + timedelta(minutes=minutes)
    world_state.current_time = format_time(updated_dt)
