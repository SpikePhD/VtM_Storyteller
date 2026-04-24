from __future__ import annotations

from dataclasses import asdict
import json
import re

from .exceptions import ContextBuildError
from .models import EventLogEntry
from .scene_models import SceneNarrationPayload, SceneNPC, SceneSnapshot
from .world_state import WorldState


def build_scene_snapshot(world_state: WorldState, recent_event_limit: int = 3) -> SceneSnapshot:
    location_id = world_state.player.location_id
    if location_id is None:
        raise ContextBuildError("player has no current location")

    location = world_state.locations.get(location_id)
    if location is None:
        raise ContextBuildError(f"player location '{location_id}' does not exist")

    npcs_present = [
        SceneNPC(
            id=npc.id,
            name=npc.name,
            role=npc.role,
            attitude_to_player=npc.attitude_to_player,
            trust_level=npc.trust_level,
        )
        for npc in sorted(
            (npc for npc in world_state.npcs.values() if npc.location_id == location_id),
            key=lambda npc: npc.id,
        )
    ]

    active_plots = sorted(
        f"{plot.name} [{plot.stage}]"
        for plot in world_state.plots.values()
        if plot.active
    )

    resolved_plots = sorted(
        f"{plot.name}: {plot.resolution_summary}"
        for plot in world_state.plots.values()
        if not plot.active and plot.resolution_summary
    )

    exits = sorted(
        {
            connected_location.name
            for connected_id in location.connected_locations
            if (connected_location := world_state.locations.get(connected_id)) is not None
        }
    )

    recent_events = _player_facing_recent_events(world_state.event_log, recent_event_limit)

    return SceneSnapshot(
        timestamp=world_state.current_time,
        player_name=world_state.player.name,
        player_clan=world_state.player.clan,
        player_hunger=world_state.player.hunger,
        player_health=world_state.player.health,
        player_willpower=world_state.player.willpower,
        player_humanity=world_state.player.humanity,
        location_id=location.id,
        location_name=location.name,
        location_type=location.type,
        location_danger_level=location.danger_level,
        location_scene_hook=location.scene_hook,
        location_notable_features=list(location.notable_features),
        location_flavor_tags=list(location.flavor_tags),
        exits=exits,
        npcs_present=npcs_present,
        active_plots=active_plots,
        resolved_plots=resolved_plots,
        recent_events=recent_events,
    )


def snapshot_to_prompt_text(snapshot: SceneSnapshot) -> str:
    lines: list[str] = [
        f"Time: {snapshot.timestamp}",
        (
            "Player: "
            f"{snapshot.player_name} | Clan: {snapshot.player_clan} | "
            f"Hunger: {snapshot.player_hunger} | Health: {snapshot.player_health} | "
            f"Willpower: {snapshot.player_willpower} | Humanity: {snapshot.player_humanity}"
        ),
        (
            "Location: "
            f"{snapshot.location_name} | ID: {snapshot.location_id} | "
            f"Type: {snapshot.location_type} | Danger: {snapshot.location_danger_level}"
        ),
        "Exits: " + (", ".join(snapshot.exits) if snapshot.exits else "None"),
        "NPCs Present: "
        + (
            "; ".join(
                f"{npc.name} ({npc.role}, attitude: {npc.attitude_to_player}, trust: {npc.trust_level})"
                for npc in snapshot.npcs_present
            )
            if snapshot.npcs_present
            else "None"
        ),
        "Active Plots: " + (", ".join(snapshot.active_plots) if snapshot.active_plots else "None"),
        "Recent Events: "
        + (
            " | ".join(snapshot.recent_events)
            if snapshot.recent_events
            else "None"
        ),
    ]
    return "\n".join(lines)


def _player_facing_recent_events(
    event_log: list[EventLogEntry],
    recent_event_limit: int,
) -> list[str]:
    if recent_event_limit <= 0:
        return []

    summarized_events = [
        summary
        for entry in event_log
        if (summary := _player_facing_event_summary(entry.description)) is not None
    ]
    return summarized_events[-recent_event_limit:]


def _player_facing_event_summary(description: str) -> str | None:
    if _is_raw_roll_event(description):
        return None

    dialogue_success = re.match(r"^Dialogue check success: (?P<npc>.+?) shares the dock lead\b", description)
    if dialogue_success is not None:
        return f"{dialogue_success.group('npc')} shared the dock lead."

    dialogue_productive = re.match(r"^Dialogue check success: (?P<npc>.+?) keeps talking\b", description)
    if dialogue_productive is not None:
        return f"{dialogue_productive.group('npc')} kept the conversation productive."

    dialogue_failed_guarded = re.match(r"^Dialogue check failed: (?P<npc>.+?) stays guarded\b", description)
    if dialogue_failed_guarded is not None:
        return f"{dialogue_failed_guarded.group('npc')} stayed guarded."

    dialogue_failed_refusal = re.match(r"^Dialogue check failed: (?P<npc>.+?) refuses\b", description)
    if dialogue_failed_refusal is not None:
        return f"{dialogue_failed_refusal.group('npc')} refused to move past the guarded topic."

    return description


def _is_raw_roll_event(description: str) -> bool:
    return re.match(r"^Rolled [a-z_]+ check:", description) is not None


def snapshot_to_narration_payload(snapshot: SceneSnapshot) -> SceneNarrationPayload:
    return SceneNarrationPayload(
        timestamp=snapshot.timestamp,
        player_name=snapshot.player_name,
        player_clan=snapshot.player_clan,
        location_name=snapshot.location_name,
        location_scene_hook=snapshot.location_scene_hook,
        location_notable_features=list(snapshot.location_notable_features),
        location_flavor_tags=list(snapshot.location_flavor_tags),
        exits=list(snapshot.exits),
        npcs_present=list(snapshot.npcs_present),
        active_plots=list(snapshot.active_plots),
        resolved_plots=list(snapshot.resolved_plots),
        recent_events=list(snapshot.recent_events),
    )


def narration_payload_to_prompt_json(payload: SceneNarrationPayload) -> str:
    return json.dumps(asdict(payload), ensure_ascii=True, separators=(",", ":"))


def snapshot_to_footer_text(snapshot: SceneSnapshot) -> str:
    lines: list[str] = [
        f"Location: {snapshot.location_name}",
        "Exits: " + (", ".join(snapshot.exits) if snapshot.exits else "None"),
        "NPCs Present: "
        + (
            ", ".join(
                f"{npc.name} ({npc.role}, trust: {npc.trust_level})"
                for npc in snapshot.npcs_present
            )
            if snapshot.npcs_present
            else "None"
        ),
        "Active Plots: " + (", ".join(snapshot.active_plots) if snapshot.active_plots else "None"),
        "Recent Events: "
        + (
            " | ".join(snapshot.recent_events)
            if snapshot.recent_events
            else "None"
        ),
    ]
    return "\n".join(lines)
