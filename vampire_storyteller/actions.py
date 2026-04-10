from __future__ import annotations

from .hunger_engine import apply_hunger_for_elapsed_time
from .models import EventLogEntry
from .time_engine import advance_time
from .world_state import WorldState


def wait_action(world_state: WorldState, minutes: int) -> None:
    if minutes <= 0:
        raise ValueError("minutes must be > 0")

    advance_time(world_state, minutes)
    apply_hunger_for_elapsed_time(world_state, minutes)

    involved_entities = [world_state.player.id]
    if world_state.player.location_id is not None:
        involved_entities.append(world_state.player.location_id)

    world_state.append_event(
        EventLogEntry(
            timestamp=world_state.current_time,
            description=f"Player waited for {minutes} minutes.",
            involved_entities=involved_entities,
        )
    )
