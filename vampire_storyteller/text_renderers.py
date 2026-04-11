from __future__ import annotations

from .context_builder import build_scene_snapshot, snapshot_to_prompt_text
from .world_state import WorldState


def render_scene_text(world_state: WorldState) -> str:
    snapshot = build_scene_snapshot(world_state)
    return snapshot_to_prompt_text(snapshot)


def render_status_text(world_state: WorldState) -> str:
    location_id = world_state.player.location_id
    if location_id is None:
        location_text = "None"
    else:
        location = world_state.locations.get(location_id)
        location_text = location.name if location is not None else location_id

    lines = [
        f"Player: {world_state.player.name}",
        f"Clan: {world_state.player.clan}",
        f"Location: {location_text}",
        f"Time: {world_state.current_time}",
        f"Hunger: {world_state.player.hunger}",
        f"Health: {world_state.player.health}",
        f"Willpower: {world_state.player.willpower}",
        f"Humanity: {world_state.player.humanity}",
    ]
    return "\n".join(lines)


def render_help_text() -> str:
    return "\n".join(
        [
            "look",
            "status",
            "help",
            "move <destination_id>",
            "wait <minutes>",
            "talk <npc_id>",
            "investigate",
            "save",
            "load",
            "quit",
        ]
    )
