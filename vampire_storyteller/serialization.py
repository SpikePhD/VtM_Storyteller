from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .models import EventLogEntry, Location, NPC, Player, PlotThread
from .world_state import WorldState


def save_world_state(world_state: WorldState, path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(asdict(world_state), handle, indent=2, sort_keys=True)


def load_world_state(path: str | Path) -> WorldState:
    source = Path(path)
    with source.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return _world_state_from_dict(data)


def _world_state_from_dict(data: dict[str, Any]) -> WorldState:
    return WorldState(
        player=_player_from_dict(data["player"]),
        npcs={npc_id: _npc_from_dict(npc_data) for npc_id, npc_data in data.get("npcs", {}).items()},
        locations={
            location_id: _location_from_dict(location_data)
            for location_id, location_data in data.get("locations", {}).items()
        },
        plots={plot_id: _plot_thread_from_dict(plot_data) for plot_id, plot_data in data.get("plots", {}).items()},
        story_flags=[flag for flag in data.get("story_flags", []) if isinstance(flag, str) and flag],
        current_time=data.get("current_time", ""),
        event_log=[_event_log_entry_from_dict(entry) for entry in data.get("event_log", [])],
    )


def _player_from_dict(data: dict[str, Any]) -> Player:
    return Player(
        id=data["id"],
        name=data["name"],
        clan=data["clan"],
        profession=data["profession"],
        hunger=data["hunger"],
        health=data["health"],
        willpower=data["willpower"],
        humanity=data["humanity"],
        inventory=list(data.get("inventory", [])),
        location_id=data.get("location_id"),
        stats=dict(data.get("stats", {})),
    )


def _npc_from_dict(data: dict[str, Any]) -> NPC:
    return NPC(
        id=data["id"],
        name=data["name"],
        role=data["role"],
        location_id=data.get("location_id"),
        attitude_to_player=data["attitude_to_player"],
        trust_level=data.get("trust_level", 0),
        consumed_dialogue_hooks=list(data.get("consumed_dialogue_hooks", [])),
        goals=list(data.get("goals", [])),
        investigation_hint=data.get("investigation_hint", ""),
        schedule=dict(data.get("schedule", {})),
        traits=dict(data.get("traits", {})),
    )


def _location_from_dict(data: dict[str, Any]) -> Location:
    return Location(
        id=data["id"],
        name=data["name"],
        type=data["type"],
        connected_locations=list(data.get("connected_locations", [])),
        travel_time=dict(data.get("travel_time", {})),
        danger_level=data["danger_level"],
        scene_hook=_optional_str(data, "scene_hook"),
        notable_features=_optional_string_list(data, "notable_features"),
        flavor_tags=_optional_string_list(data, "flavor_tags"),
    )


def _plot_thread_from_dict(data: dict[str, Any]) -> PlotThread:
    return PlotThread(
        id=data["id"],
        name=data["name"],
        stage=data["stage"],
        active=data["active"],
        triggers=list(data.get("triggers", [])),
        consequences=list(data.get("consequences", [])),
        resolution_summary=_optional_str(data, "resolution_summary"),
        learned_outcome=_optional_str(data, "learned_outcome"),
        closing_beat=_optional_str(data, "closing_beat"),
    )


def _event_log_entry_from_dict(data: dict[str, Any]) -> EventLogEntry:
    return EventLogEntry(
        timestamp=data["timestamp"],
        description=data["description"],
        involved_entities=list(data.get("involved_entities", [])),
    )


def _optional_str(data: dict[str, Any], field_name: str) -> str:
    value = data.get(field_name, "")
    return value if isinstance(value, str) else ""


def _optional_string_list(data: dict[str, Any], field_name: str) -> list[str]:
    value = data.get(field_name, [])
    if not isinstance(value, list):
        return []
    return [entry for entry in value if isinstance(entry, str) and entry]
