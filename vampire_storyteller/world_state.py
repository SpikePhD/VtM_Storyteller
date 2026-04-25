from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .command_models import ConversationStance
from .models import EventLogEntry, Location, NPC, NPCDialogueProfile, Player, PlotThread
from .plot_stage_semantics import PlotStageSemantics
from .social_models import NPCSocialState, TopicSensitivity


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
        _require_mapping(data, "world state")
        return cls(
            player=_player_from_dict(_require_mapping(_require_present_value(data, "player"), "player")),
            npcs={
                npc_id: _npc_from_dict(_require_mapping(npc_data, f"npc '{npc_id}'"))
                for npc_id, npc_data in _require_mapping(_require_present_value(data, "npcs"), "npcs").items()
            },
            locations={
                location_id: _location_from_dict(location_data)
                for location_id, location_data in _require_mapping(_require_present_value(data, "locations"), "locations").items()
            },
            plots={
                plot_id: _plot_thread_from_dict(_require_mapping(plot_data, f"plot '{plot_id}'"))
                for plot_id, plot_data in _require_mapping(_require_present_value(data, "plots"), "plots").items()
            },
            story_flags=_require_string_list(_require_present_value(data, "story_flags"), "story_flags"),
            current_time=_require_iso_datetime(_require_str(data, "current_time", "current_time")),
            event_log=[
                _event_log_entry_from_dict(_require_mapping(entry, f"event log entry {index}"))
                for index, entry in enumerate(_require_list(_require_present_value(data, "event_log"), "event_log"))
            ],
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
        "previous_interactions_summary": npc.previous_interactions_summary,
        "consumed_dialogue_hooks": list(npc.consumed_dialogue_hooks),
        "goals": list(npc.goals),
        "investigation_hint": npc.investigation_hint,
        "schedule": dict(npc.schedule),
        "traits": dict(npc.traits),
        "dialogue_profile": _npc_dialogue_profile_to_dict(npc.dialogue_profile),
        "social_state": _npc_social_state_to_dict(npc.social_state),
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
        "stage_semantics": {stage_id: _plot_stage_semantics_to_dict(semantics) for stage_id, semantics in plot.stage_semantics.items()},
    }


def _event_log_entry_to_dict(entry: EventLogEntry) -> dict[str, Any]:
    return {
        "timestamp": entry.timestamp,
        "description": entry.description,
        "involved_entities": list(entry.involved_entities),
    }


def _player_from_dict(data: dict[str, Any]) -> Player:
    return Player(
        id=_require_str(data, "id"),
        name=_require_str(data, "name"),
        clan=_require_str(data, "clan"),
        profession=_require_str(data, "profession"),
        hunger=_require_int(data, "hunger"),
        health=_require_int(data, "health"),
        willpower=_require_int(data, "willpower"),
        humanity=_require_int(data, "humanity"),
        inventory=_require_string_list(_require_present_value(data, "inventory"), "inventory"),
        location_id=_require_optional_str(data, "location_id"),
        stats=_require_int_mapping(_require_present_value(data, "stats"), "stats"),
    )


def _npc_from_dict(data: dict[str, Any]) -> NPC:
    attitude_to_player = _require_str(data, "attitude_to_player")
    trust_level = _require_int(data, "trust_level")
    return NPC(
        id=_require_str(data, "id"),
        name=_require_str(data, "name"),
        role=_require_str(data, "role"),
        location_id=_require_optional_str(data, "location_id"),
        attitude_to_player=attitude_to_player,
        trust_level=trust_level,
        previous_interactions_summary=_require_optional_text_field(data, "previous_interactions_summary"),
        consumed_dialogue_hooks=_require_string_list(_require_present_value(data, "consumed_dialogue_hooks"), "consumed_dialogue_hooks"),
        goals=_require_string_list(_require_present_value(data, "goals"), "goals"),
        investigation_hint=_require_str(data, "investigation_hint", "investigation_hint"),
        schedule=_require_str_mapping(_require_present_value(data, "schedule"), "schedule"),
        traits=_require_str_mapping(_require_present_value(data, "traits"), "traits"),
        dialogue_profile=_npc_dialogue_profile_from_dict(data.get("dialogue_profile")),
        social_state=_npc_social_state_from_dict(data.get("social_state"), attitude_to_player, trust_level),
    )


def _npc_dialogue_profile_to_dict(profile: NPCDialogueProfile) -> dict[str, Any]:
    return {
        "background_summary": profile.background_summary,
        "public_persona": profile.public_persona,
        "private_history_summary": profile.private_history_summary,
        "motivations": list(profile.motivations),
        "speaking_style": profile.speaking_style,
        "relationship_context": profile.relationship_context,
    }


def _npc_dialogue_profile_from_dict(data: Any) -> NPCDialogueProfile:
    if data is None:
        return NPCDialogueProfile()
    if not isinstance(data, dict):
        raise TypeError("dialogue_profile must be a JSON object.")
    return NPCDialogueProfile(
        background_summary=_require_optional_text_field(data, "background_summary"),
        public_persona=_require_optional_text_field(data, "public_persona"),
        private_history_summary=_require_optional_text_field(data, "private_history_summary"),
        motivations=_require_optional_string_list(data, "motivations"),
        speaking_style=_require_optional_text_field(data, "speaking_style"),
        relationship_context=_require_optional_text_field(data, "relationship_context"),
    )


def _location_from_dict(data: dict[str, Any]) -> Location:
    return Location(
        id=_require_str(data, "id"),
        name=_require_str(data, "name"),
        type=_require_str(data, "type"),
        connected_locations=_require_string_list(_require_present_value(data, "connected_locations"), "connected_locations"),
        travel_time=_require_int_mapping(_require_present_value(data, "travel_time"), "travel_time"),
        danger_level=_require_int(data, "danger_level"),
        scene_hook=_require_present_str(data, "scene_hook"),
        notable_features=_require_string_list(_require_present_value(data, "notable_features"), "notable_features"),
        flavor_tags=_require_string_list(_require_present_value(data, "flavor_tags"), "flavor_tags"),
    )


def _plot_thread_from_dict(data: dict[str, Any]) -> PlotThread:
    return PlotThread(
        id=_require_str(data, "id"),
        name=_require_str(data, "name"),
        stage=_require_str(data, "stage"),
        active=_require_bool(data, "active"),
        triggers=_require_string_list(_require_present_value(data, "triggers"), "triggers"),
        consequences=_require_string_list(_require_present_value(data, "consequences"), "consequences"),
        resolution_summary=_require_present_str(data, "resolution_summary"),
        learned_outcome=_require_present_str(data, "learned_outcome"),
        closing_beat=_require_present_str(data, "closing_beat"),
        stage_semantics=_plot_stage_semantics_from_dict(data.get("stage_semantics")),
    )


def _event_log_entry_from_dict(data: dict[str, Any]) -> EventLogEntry:
    return EventLogEntry(
        timestamp=_require_iso_datetime(_require_str(data, "timestamp", "timestamp")),
        description=_require_str(data, "description"),
        involved_entities=_require_string_list(_require_present_value(data, "involved_entities"), "involved_entities"),
    )


def _npc_social_state_to_dict(social_state: NPCSocialState) -> dict[str, Any]:
    return {
        "relationship_to_player": social_state.relationship_to_player,
        "trust": social_state.trust,
        "hostility": social_state.hostility,
        "fear": social_state.fear,
        "respect": social_state.respect,
        "willingness_to_cooperate": social_state.willingness_to_cooperate,
        "current_conversation_stance": social_state.current_conversation_stance.value,
        "topic_sensitivity": {topic: sensitivity.value for topic, sensitivity in social_state.topic_sensitivity.items()},
    }


def _plot_stage_semantics_to_dict(semantics: PlotStageSemantics) -> dict[str, Any]:
    return {
        "stage_id": semantics.stage_id,
        "semantic_category": semantics.semantic_category,
        "player_summary": semantics.player_summary,
        "prompt_guidance": semantics.prompt_guidance,
        "allowed_specificity": semantics.allowed_specificity,
    }


def _plot_stage_semantics_from_dict(value: Any) -> dict[str, PlotStageSemantics]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise TypeError("stage_semantics must be a JSON object.")

    semantics: dict[str, PlotStageSemantics] = {}
    for stage_id, semantics_data in value.items():
        if not isinstance(stage_id, str) or not stage_id:
            raise TypeError("stage_semantics must use non-empty string keys.")
        if not isinstance(semantics_data, dict):
            raise TypeError(f"stage_semantics for '{stage_id}' must be a JSON object.")
        semantics[stage_id] = PlotStageSemantics(
            stage_id=_require_optional_str(semantics_data, "stage_id") or stage_id,
            semantic_category=_require_str(semantics_data, "semantic_category"),
            player_summary=_require_str(semantics_data, "player_summary"),
            prompt_guidance=_require_str(semantics_data, "prompt_guidance"),
            allowed_specificity=_require_str(semantics_data, "allowed_specificity"),
        )
    return semantics


def _npc_social_state_from_dict(
    data: Any,
    attitude_to_player: str,
    trust_level: int,
) -> NPCSocialState:
    if data is None:
        return NPCSocialState(
            relationship_to_player=attitude_to_player,
            trust=trust_level,
        )
    if not isinstance(data, dict):
        raise TypeError("social_state must be a JSON object.")

    topic_sensitivity_raw = data.get("topic_sensitivity", {})
    if not isinstance(topic_sensitivity_raw, dict):
        raise TypeError("topic_sensitivity must be a JSON object.")
    topic_sensitivity: dict[str, TopicSensitivity] = {}
    for topic, sensitivity in topic_sensitivity_raw.items():
        if not isinstance(topic, str) or not topic:
            raise TypeError("topic_sensitivity must use non-empty string keys.")
        if not isinstance(sensitivity, str):
            raise TypeError("topic_sensitivity must use string values.")
        topic_sensitivity[topic] = TopicSensitivity(sensitivity)

    stance_value = data.get("current_conversation_stance", "neutral")
    if not isinstance(stance_value, str):
        raise TypeError("current_conversation_stance must be a string.")

    return NPCSocialState(
        relationship_to_player=_require_social_str(data, "relationship_to_player", attitude_to_player),
        trust=_require_social_int(data, "trust", trust_level),
        hostility=_require_social_int(data, "hostility", 0),
        fear=_require_social_int(data, "fear", 0),
        respect=_require_social_int(data, "respect", 0),
        willingness_to_cooperate=_require_social_int(data, "willingness_to_cooperate", 0),
        current_conversation_stance=ConversationStance(stance_value),
        topic_sensitivity=topic_sensitivity,
    )


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be a JSON object.")
    return value


def _require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise TypeError(f"{label} must be a JSON array.")
    return value


def _require_present_value(data: dict[str, Any], field_name: str) -> Any:
    if field_name not in data:
        raise TypeError(f"{field_name} is required.")
    return data[field_name]


def _require_str(data: dict[str, Any], field_name: str, label: str | None = None) -> str:
    if field_name not in data:
        raise TypeError(f"{label or field_name} is required.")
    value = data[field_name]
    if not isinstance(value, str) or not value:
        raise TypeError(f"{label or field_name} must be a non-empty string.")
    return value


def _require_present_str(data: dict[str, Any], field_name: str) -> str:
    if field_name not in data:
        raise TypeError(f"{field_name} is required.")
    value = data[field_name]
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string.")
    return value


def _require_optional_str(data: dict[str, Any], field_name: str) -> str | None:
    if field_name not in data:
        raise TypeError(f"{field_name} is required.")
    value = data[field_name]
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string or null.")
    return value


def _require_int(data: dict[str, Any], field_name: str) -> int:
    if field_name not in data:
        raise TypeError(f"{field_name} is required.")
    value = data[field_name]
    if not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer.")
    return value


def _require_bool(data: dict[str, Any], field_name: str) -> bool:
    if field_name not in data:
        raise TypeError(f"{field_name} is required.")
    value = data[field_name]
    if not isinstance(value, bool):
        raise TypeError(f"{field_name} must be a boolean.")
    return value


def _require_string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        raise TypeError(f"{label} must be a JSON array.")

    validated: list[str] = []
    for entry in value:
        if not isinstance(entry, str):
            raise TypeError(f"{label} must contain only strings.")
        validated.append(entry)
    return validated


def _require_optional_string_list(data: dict[str, Any], field_name: str) -> list[str]:
    if field_name not in data:
        return []
    return _require_string_list(data[field_name], field_name)


def _require_int_mapping(value: Any, label: str) -> dict[str, int]:
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be a JSON object.")

    validated: dict[str, int] = {}
    for key, entry in value.items():
        if not isinstance(key, str) or not key:
            raise TypeError(f"{label} must use non-empty string keys.")
        if not isinstance(entry, int):
            raise TypeError(f"{label} must use integer values.")
        validated[key] = entry
    return validated


def _require_str_mapping(value: Any, label: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be a JSON object.")

    validated: dict[str, str] = {}
    for key, entry in value.items():
        if not isinstance(key, str) or not key:
            raise TypeError(f"{label} must use non-empty string keys.")
        if not isinstance(entry, str):
            raise TypeError(f"{label} must use string values.")
        validated[key] = entry
    return validated


def _require_optional_text_field(data: dict[str, Any], field_name: str) -> str:
    value = data.get(field_name, "")
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string.")
    return value


def _require_social_str(data: dict[str, Any], field_name: str, default: str) -> str:
    value = data.get(field_name, default)
    if not isinstance(value, str) or not value:
        raise TypeError(f"{field_name} must be a non-empty string.")
    return value


def _require_social_int(data: dict[str, Any], field_name: str, default: int) -> int:
    value = data.get(field_name, default)
    if not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer.")
    return value


def _require_iso_datetime(value: str) -> str:
    from datetime import datetime

    try:
        datetime.fromisoformat(value)
    except ValueError as exc:
        raise TypeError(f"current_time must be a valid ISO datetime.") from exc
    return value
