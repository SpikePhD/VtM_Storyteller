from __future__ import annotations

from .exceptions import InvalidLocationError, MovementError
from .models import EventLogEntry
from .time_engine import advance_time
from .world_state import WorldState


def move_player(world_state: WorldState, destination_id: str) -> None:
    source_location_id = world_state.player.location_id
    if source_location_id is None:
        raise MovementError("player has no current location")

    source_location = world_state.locations.get(source_location_id)
    if source_location is None:
        raise MovementError(f"source location '{source_location_id}' does not exist")

    destination = world_state.locations.get(destination_id)
    if destination is None:
        raise InvalidLocationError(f"destination '{destination_id}' does not exist")

    if destination_id not in source_location.connected_locations:
        raise MovementError(
            f"destination '{destination_id}' is not connected to source '{source_location_id}'"
        )

    travel_minutes = source_location.travel_time.get(destination_id)
    if travel_minutes is None:
        raise MovementError(
            f"travel time from '{source_location_id}' to '{destination_id}' is not defined"
        )

    advance_time(world_state, travel_minutes)
    world_state.player.location_id = destination_id
    world_state.append_event(
        EventLogEntry(
            timestamp=world_state.current_time,
            description=f"Player moved from {source_location.name} to {destination.name}.",
            involved_entities=[world_state.player.id, source_location_id, destination_id],
        )
    )
