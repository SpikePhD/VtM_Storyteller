from __future__ import annotations

from datetime import datetime, time

from .models import EventLogEntry
from .world_state import WorldState


def get_time_band(timestamp: str) -> str | None:
    """Return the active scheduling band for an ISO timestamp."""

    try:
        parsed = datetime.fromisoformat(timestamp)
    except ValueError:
        return None

    current_time = parsed.time()
    if time(18, 0) <= current_time <= time(20, 59, 59, 999999):
        return "evening"
    if time(21, 0) <= current_time <= time(22, 59, 59, 999999):
        return "night"
    if time(23, 0) <= current_time or current_time <= time(0, 59, 59, 999999):
        return "late"
    if time(1, 0) <= current_time <= time(3, 59, 59, 999999):
        return "midnight"
    return None


def update_npcs_for_current_time(world_state: WorldState) -> list[str]:
    """Move NPCs according to the current time band and return messages."""

    time_band = get_time_band(world_state.current_time)
    if time_band is None:
        return []

    messages: list[str] = []
    for npc in world_state.npcs.values():
        destination_id = npc.schedule.get(time_band)
        if destination_id is None:
            continue
        if destination_id not in world_state.locations:
            continue
        if npc.location_id == destination_id:
            continue

        npc.location_id = destination_id
        world_state.append_event(
            EventLogEntry(
                timestamp=world_state.current_time,
                description=f"NPC '{npc.name}' moved to {world_state.locations[destination_id].name} for {time_band}.",
                involved_entities=[npc.id, destination_id],
            )
        )
        messages.append(f"{npc.name} moved to {world_state.locations[destination_id].name}.")

    return messages
