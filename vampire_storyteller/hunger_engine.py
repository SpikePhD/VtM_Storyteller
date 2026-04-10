from __future__ import annotations

from .models import EventLogEntry
from .world_state import WorldState


def apply_hunger_for_elapsed_time(world_state: WorldState, elapsed_minutes: int) -> None:
    if elapsed_minutes < 0:
        raise ValueError("elapsed_minutes must be >= 0")
    if elapsed_minutes == 0:
        return

    hunger_gain = elapsed_minutes // 60
    if hunger_gain <= 0:
        return

    previous_hunger = world_state.player.hunger
    updated_hunger = min(5, previous_hunger + hunger_gain)
    if updated_hunger == previous_hunger:
        return

    world_state.player.hunger = updated_hunger
    world_state.append_event(
        EventLogEntry(
            timestamp=world_state.current_time,
            description=f"Player hunger increased from {previous_hunger} to {updated_hunger}.",
            involved_entities=[world_state.player.id],
        )
    )
