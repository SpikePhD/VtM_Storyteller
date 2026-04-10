from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .data_paths import ADVENTURE_ID, get_adventure_root
from .models import Location, NPC, Player, PlotThread
from .world_state import WorldState


class AdventureContentError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PlotProgressionRules:
    plot_id: str
    plot_name: str
    move_from_stage: str
    move_destination_id: str
    move_to_stage: str
    wait_from_stage: str
    wait_location_id: str
    wait_minimum_minutes: int
    wait_to_stage: str


@dataclass(frozen=True, slots=True)
class PlotInvestigationRules:
    plot_id: str
    plot_name: str
    location_id: str
    required_stage: str
    requires_roll: bool
    roll_pool: int
    difficulty: int
    success_stage: str
    success_active: bool
    success_message: str
    failure_message: str


@dataclass(frozen=True, slots=True)
class Adv1WorldSeedData:
    current_time: str


@dataclass(frozen=True, slots=True)
class Adv1PlayerSeedData:
    player: Player


@dataclass(frozen=True, slots=True)
class Adv1NpcDefinition:
    id: str
    name: str
    role: str
    starting_location_id: str
    attitude_to_player: str
    traits: dict[str, str]
    schedule: dict[str, str]


@dataclass(frozen=True, slots=True)
class Adv1LocationDefinition:
    id: str
    name: str
    type: str
    connected_locations: list[str]
    travel_time: dict[str, int]
    danger_level: int


@dataclass(frozen=True, slots=True)
class Adv1PlotThreadDefinition:
    id: str
    name: str
    stage: str
    active: bool
    triggers: list[str]
    consequences: list[str]


def load_adv1_world_state(adventure_root: Path | None = None) -> WorldState:
    root = get_adventure_root() if adventure_root is None else Path(adventure_root)
    _validate_adventure_metadata(_read_json(root / "config" / "adventure.json"))

    seed_data = load_adv1_world_seed_data(root)
    player_seed = load_adv1_player_seed_data(root)
    location_definitions = load_adv1_location_definitions(root)
    plot_thread_definitions = load_adv1_plot_thread_definitions(root)
    npc_definitions = load_adv1_npc_definitions(root)

    return WorldState(
        player=player_seed.player,
        npcs={npc_definition.id: _npc_from_definition(npc_definition) for npc_definition in npc_definitions},
        locations={location_definition.id: _location_from_definition(location_definition) for location_definition in location_definitions},
        plots={plot_definition.id: _plot_from_definition(plot_definition) for plot_definition in plot_thread_definitions},
        current_time=seed_data.current_time,
    )


def load_adv1_player_seed_data(adventure_root: Path | None = None) -> Adv1PlayerSeedData:
    root = get_adventure_root() if adventure_root is None else Path(adventure_root)
    player_data = _read_json(root / "world" / "player.json")

    return Adv1PlayerSeedData(player=_player_from_dict(player_data))


def load_adv1_world_seed_data(adventure_root: Path | None = None) -> Adv1WorldSeedData:
    root = get_adventure_root() if adventure_root is None else Path(adventure_root)
    time_data = _read_json(root / "world" / "time.json")

    return Adv1WorldSeedData(current_time=_require_str(time_data, "current_time"))


def load_adv1_location_definitions(adventure_root: Path | None = None) -> list[Adv1LocationDefinition]:
    root = get_adventure_root() if adventure_root is None else Path(adventure_root)
    data = _read_json(root / "locations" / "locations.json")
    location_entries = data.get("locations")
    if not isinstance(location_entries, list):
        raise AdventureContentError("Adventure field 'locations' must be a JSON array.")

    definitions: list[Adv1LocationDefinition] = []
    for location_data in location_entries:
        if not isinstance(location_data, dict):
            raise AdventureContentError("Adventure location entries must be JSON objects.")
        definitions.append(_location_definition_from_dict(location_data))
    return definitions


def load_adv1_plot_thread_definitions(adventure_root: Path | None = None) -> list[Adv1PlotThreadDefinition]:
    root = get_adventure_root() if adventure_root is None else Path(adventure_root)
    data = _read_json(root / "plots" / "plot_threads.json")
    plot_entries = data.get("plots")
    if not isinstance(plot_entries, list):
        raise AdventureContentError("Adventure field 'plots' must be a JSON array.")

    definitions: list[Adv1PlotThreadDefinition] = []
    for plot_data in plot_entries:
        if not isinstance(plot_data, dict):
            raise AdventureContentError("Adventure plot entries must be JSON objects.")
        definitions.append(_plot_thread_definition_from_dict(plot_data))
    return definitions


def load_adv1_npc_definitions(adventure_root: Path | None = None) -> list[Adv1NpcDefinition]:
    root = get_adventure_root() if adventure_root is None else Path(adventure_root)
    data = _read_json(root / "npcs" / "npcs.json")
    npc_entries = data.get("npcs")
    if not isinstance(npc_entries, list):
        raise AdventureContentError("Adventure field 'npcs' must be a JSON array.")

    definitions: list[Adv1NpcDefinition] = []
    for npc_data in npc_entries:
        if not isinstance(npc_data, dict):
            raise AdventureContentError("Adventure NPC entries must be JSON objects.")
        definitions.append(_npc_definition_from_dict(npc_data))
    return definitions


def load_adv1_plot_progression_rules(adventure_root: Path | None = None) -> PlotProgressionRules:
    root = get_adventure_root() if adventure_root is None else Path(adventure_root)
    data = _read_json(root / "plots" / "plot_progression.json")
    _validate_plot_rule_metadata(data)
    move_rule = _require_mapping(data, "move")
    wait_rule = _require_mapping(data, "wait")

    return PlotProgressionRules(
        plot_id=_require_str(data, "plot_id"),
        plot_name=_require_str(data, "plot_name"),
        move_from_stage=_require_str(move_rule, "from_stage"),
        move_destination_id=_require_str(move_rule, "destination_id"),
        move_to_stage=_require_str(move_rule, "to_stage"),
        wait_from_stage=_require_str(wait_rule, "from_stage"),
        wait_location_id=_require_str(wait_rule, "location_id"),
        wait_minimum_minutes=_require_int(wait_rule, "minimum_minutes"),
        wait_to_stage=_require_str(wait_rule, "to_stage"),
    )


def load_adv1_plot_investigation_rules(adventure_root: Path | None = None) -> PlotInvestigationRules:
    root = get_adventure_root() if adventure_root is None else Path(adventure_root)
    data = _read_json(root / "plots" / "plot_resolution.json")
    _validate_plot_rule_metadata(data)
    investigate_rule = _require_mapping(data, "investigate")
    success_rule = _require_mapping(investigate_rule, "success")
    failure_rule = _require_mapping(investigate_rule, "failure")

    return PlotInvestigationRules(
        plot_id=_require_str(data, "plot_id"),
        plot_name=_require_str(data, "plot_name"),
        location_id=_require_str(investigate_rule, "location_id"),
        required_stage=_require_str(investigate_rule, "required_stage"),
        requires_roll=_require_bool(investigate_rule, "requires_roll"),
        roll_pool=_require_int(investigate_rule, "roll_pool"),
        difficulty=_require_int(investigate_rule, "difficulty"),
        success_stage=_require_str(success_rule, "to_stage"),
        success_active=_require_bool(success_rule, "active"),
        success_message=_require_str(success_rule, "message"),
        failure_message=_require_str(failure_rule, "message"),
    )


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise AdventureContentError(f"Required adventure file missing: {path.as_posix()}")

    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        raise AdventureContentError(f"Malformed adventure file: {path.as_posix()}") from exc

    if not isinstance(data, dict):
        raise AdventureContentError(f"Adventure file must contain a JSON object: {path.as_posix()}")
    return data


def _require_mapping(data: dict[str, Any], field_name: str) -> dict[str, Any]:
    value = data.get(field_name)
    if not isinstance(value, dict):
        raise AdventureContentError(f"Adventure field '{field_name}' must be a JSON object.")
    return value


def _require_string_mapping(data: dict[str, Any], field_name: str) -> dict[str, str]:
    mapping = _require_mapping(data, field_name)
    validated_mapping: dict[str, str] = {}
    for key, value in mapping.items():
        if not isinstance(key, str) or not key:
            raise AdventureContentError(f"Adventure field '{field_name}' must use non-empty string keys.")
        if not isinstance(value, str) or not value:
            raise AdventureContentError(f"Adventure field '{field_name}' must use non-empty string values.")
        validated_mapping[key] = value
    return validated_mapping


def _require_str(data: dict[str, Any], field_name: str) -> str:
    value = data.get(field_name)
    if not isinstance(value, str) or not value:
        raise AdventureContentError(f"Adventure field '{field_name}' must be a non-empty string.")
    return value


def _require_int(data: dict[str, Any], field_name: str) -> int:
    value = data.get(field_name)
    if not isinstance(value, int):
        raise AdventureContentError(f"Adventure field '{field_name}' must be an integer.")
    return value


def _require_bool(data: dict[str, Any], field_name: str) -> bool:
    value = data.get(field_name)
    if not isinstance(value, bool):
        raise AdventureContentError(f"Adventure field '{field_name}' must be a boolean.")
    return value


def _validate_adventure_metadata(data: dict[str, Any]) -> None:
    adventure_id = _require_str(data, "id")
    if adventure_id != ADVENTURE_ID:
        raise AdventureContentError(
            f"Adventure metadata id must be '{ADVENTURE_ID}', found '{adventure_id}'."
        )
    _require_str(data, "name")
    _require_str(data, "description")
    _require_str(data, "starting_world_state_source")


def _validate_plot_rule_metadata(data: dict[str, Any]) -> None:
    _require_str(data, "plot_id")
    _require_str(data, "plot_name")


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
        inventory=list(data.get("inventory", [])),
        location_id=data.get("location_id"),
        stats=dict(data.get("stats", {})),
    )


def _npc_from_dict(data: dict[str, Any]) -> NPC:
    return NPC(
        id=_require_str(data, "id"),
        name=_require_str(data, "name"),
        role=_require_str(data, "role"),
        location_id=data.get("location_id"),
        attitude_to_player=_require_str(data, "attitude_to_player"),
        goals=list(data.get("goals", [])),
        schedule=dict(data.get("schedule", {})),
        traits=dict(data.get("traits", {})),
    )


def _npc_definition_from_dict(data: dict[str, Any]) -> Adv1NpcDefinition:
    return Adv1NpcDefinition(
        id=_require_str(data, "id"),
        name=_require_str(data, "name"),
        role=_require_str(data, "role"),
        starting_location_id=_require_str(data, "starting_location_id"),
        attitude_to_player=_require_str(data, "attitude_to_player"),
        traits=_require_string_mapping(data, "traits"),
        schedule=_require_string_mapping(data, "schedule"),
    )


def _npc_from_definition(definition: Adv1NpcDefinition) -> NPC:
    return NPC(
        id=definition.id,
        name=definition.name,
        role=definition.role,
        location_id=definition.starting_location_id,
        attitude_to_player=definition.attitude_to_player,
        goals=[],
        schedule=dict(definition.schedule),
        traits=dict(definition.traits),
    )


def _location_definition_from_dict(data: dict[str, Any]) -> Adv1LocationDefinition:
    return Adv1LocationDefinition(
        id=_require_str(data, "id"),
        name=_require_str(data, "name"),
        type=_require_str(data, "type"),
        connected_locations=_require_string_list(data, "connected_locations"),
        travel_time=_require_int_mapping(data, "travel_time"),
        danger_level=_require_int(data, "danger_level"),
    )


def _location_from_definition(definition: Adv1LocationDefinition) -> Location:
    return Location(
        id=definition.id,
        name=definition.name,
        type=definition.type,
        connected_locations=list(definition.connected_locations),
        travel_time=dict(definition.travel_time),
        danger_level=definition.danger_level,
    )


def _location_from_dict(data: dict[str, Any]) -> Location:
    return Location(
        id=_require_str(data, "id"),
        name=_require_str(data, "name"),
        type=_require_str(data, "type"),
        connected_locations=_require_string_list(data, "connected_locations"),
        travel_time=_require_int_mapping(data, "travel_time"),
        danger_level=_require_int(data, "danger_level"),
    )


def _plot_from_dict(data: dict[str, Any]) -> PlotThread:
    return PlotThread(
        id=_require_str(data, "id"),
        name=_require_str(data, "name"),
        stage=_require_str(data, "stage"),
        active=_require_bool(data, "active"),
        triggers=list(data.get("triggers", [])),
        consequences=list(data.get("consequences", [])),
    )


def _plot_thread_definition_from_dict(data: dict[str, Any]) -> Adv1PlotThreadDefinition:
    return Adv1PlotThreadDefinition(
        id=_require_str(data, "id"),
        name=_require_str(data, "name"),
        stage=_require_str(data, "stage"),
        active=_require_bool(data, "active"),
        triggers=_require_string_list(data, "triggers"),
        consequences=_require_string_list(data, "consequences"),
    )


def _plot_from_definition(definition: Adv1PlotThreadDefinition) -> PlotThread:
    return PlotThread(
        id=definition.id,
        name=definition.name,
        stage=definition.stage,
        active=definition.active,
        triggers=list(definition.triggers),
        consequences=list(definition.consequences),
    )


def _require_string_list(data: dict[str, Any], field_name: str) -> list[str]:
    value = data.get(field_name)
    if not isinstance(value, list):
        raise AdventureContentError(f"Adventure field '{field_name}' must be a JSON array.")

    validated_values: list[str] = []
    for entry in value:
        if not isinstance(entry, str) or not entry:
            raise AdventureContentError(f"Adventure field '{field_name}' must contain non-empty strings.")
        validated_values.append(entry)
    return validated_values


def _require_int_mapping(data: dict[str, Any], field_name: str) -> dict[str, int]:
    mapping = _require_mapping(data, field_name)
    validated_mapping: dict[str, int] = {}
    for key, value in mapping.items():
        if not isinstance(key, str) or not key:
            raise AdventureContentError(f"Adventure field '{field_name}' must use non-empty string keys.")
        if not isinstance(value, int):
            raise AdventureContentError(f"Adventure field '{field_name}' must use integer values.")
        validated_mapping[key] = value
    return validated_mapping
