from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import EventLogEntry, Location, NPC, Player, PlotThread


@dataclass
class WorldState:
    player: Player
    npcs: dict[str, NPC] = field(default_factory=dict)
    locations: dict[str, Location] = field(default_factory=dict)
    plots: dict[str, PlotThread] = field(default_factory=dict)
    story_flags: list[str] = field(default_factory=list)
    current_time: str = ""
    event_log: list[EventLogEntry] = field(default_factory=list)

    def append_event(self, entry: EventLogEntry) -> None:
        self.event_log.append(entry)

    def add_story_flag(self, story_flag: str) -> bool:
        if story_flag in self.story_flags:
            return False
        self.story_flags.append(story_flag)
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "player": _player_to_dict(self.player),
            "npcs": {npc_id: _npc_to_dict(npc) for npc_id, npc in self.npcs.items()},
            "locations": {location_id: _location_to_dict(location) for location_id, location in self.locations.items()},
            "plots": {plot_id: _plot_thread_to_dict(plot) for plot_id, plot in self.plots.items()},
            "story_flags": list(self.story_flags),
            "current_time": self.current_time,
            "event_log": [_event_log_entry_to_dict(entry) for entry in self.event_log],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorldState:
        return cls(
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


def _player_to_dict(player: Player) -> dict[str, Any]:
    return {
        "id": player.id,
        "name": player.name,
        "clan": player.clan,
        "profession": player.profession,
        "hunger": player.hunger,
        "health": player.health,
        "willpower": player.willpower,
        "humanity": player.humanity,
        "inventory": list(player.inventory),
        "location_id": player.location_id,
        "stats": dict(player.stats),
    }


def _npc_to_dict(npc: NPC) -> dict[str, Any]:
    return {
        "id": npc.id,
        "name": npc.name,
        "role": npc.role,
        "location_id": npc.location_id,
        "attitude_to_player": npc.attitude_to_player,
        "trust_level": npc.trust_level,
        "consumed_dialogue_hooks": list(npc.consumed_dialogue_hooks),
        "goals": list(npc.goals),
        "investigation_hint": npc.investigation_hint,
        "schedule": dict(npc.schedule),
        "traits": dict(npc.traits),
    }


def _location_to_dict(location: Location) -> dict[str, Any]:
    return {
        "id": location.id,
        "name": location.name,
        "type": location.type,
        "connected_locations": list(location.connected_locations),
        "travel_time": dict(location.travel_time),
        "danger_level": location.danger_level,
        "scene_hook": location.scene_hook,
        "notable_features": list(location.notable_features),
        "flavor_tags": list(location.flavor_tags),
    }


def _plot_thread_to_dict(plot: PlotThread) -> dict[str, Any]:
    return {
        "id": plot.id,
        "name": plot.name,
        "stage": plot.stage,
        "active": plot.active,
        "triggers": list(plot.triggers),
        "consequences": list(plot.consequences),
        "resolution_summary": plot.resolution_summary,
        "learned_outcome": plot.learned_outcome,
        "closing_beat": plot.closing_beat,
    }


def _event_log_entry_to_dict(entry: EventLogEntry) -> dict[str, Any]:
    return {
        "timestamp": entry.timestamp,
        "description": entry.description,
        "involved_entities": list(entry.involved_entities),
    }


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
