from __future__ import annotations

import json
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .data_paths import ADVENTURE_ID, get_adventure_root
from .models import Location, NPC, NPCDialogueProfile, Player, PlotThread
from .command_models import ConversationStance
from .social_models import NPCSocialState, TopicSensitivity
from .world_state import WorldState


class AdventureContentError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Adv1AdventureMetadata:
    id: str
    name: str
    description: str
    starting_world_state_source: str


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
    talk_from_stage: str
    talk_npc_id: str
    talk_location_id: str
    talk_minimum_trust_level: int
    talk_required_story_flag: str
    talk_to_stage: str


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
    trust_level: int
    previous_interactions_summary: str
    social_state: NPCSocialState
    goals: list[str]
    investigation_hint: str
    traits: dict[str, str]
    schedule: dict[str, str]
    dialogue_profile: NPCDialogueProfile


@dataclass(frozen=True, slots=True)
class Adv1LocationDefinition:
    id: str
    name: str
    type: str
    connected_locations: list[str]
    travel_time: dict[str, int]
    danger_level: int
    scene_hook: str
    notable_features: list[str]
    flavor_tags: list[str]


@dataclass(frozen=True, slots=True)
class Adv1PlotThreadDefinition:
    id: str
    name: str
    stage: str
    active: bool
    triggers: list[str]
    consequences: list[str]


@dataclass(frozen=True, slots=True)
class Adv1PlotOutcomeDefinition:
    id: str
    name: str
    resolved_event_text: str
    learned_outcome: str
    closing_beat: str
    trust_adjustments: dict[str, int]


@dataclass(frozen=True, slots=True)
class Adv1DialogueHookDefinition:
    hook_id: str
    npc_id: str
    required_plot_id: str
    required_plot_stage: str
    minimum_trust_level: int
    trust_delta: int
    repeatable: bool
    required_dialogue_acts: list[str]
    story_flags_to_add: list[str]


@dataclass(frozen=True, slots=True)
class Adv1DialogueFactDefinition:
    fact_id: str
    npc_id: str
    plot_id: str | None
    subtopic: str | None
    summary: str
    kind: str
    required_plot_stages: tuple[str, ...]
    required_story_flags: tuple[str, ...]
    allowed_outcome_kinds: tuple[str, ...]
    allowed_topic_results: tuple[str, ...]
    requires_check_success: bool | None
    required_dialogue_domains: tuple[str, ...]
    required_dialogue_acts: tuple[str, ...]
    required_keywords: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Adv1DialogueFactState:
    fact_definitions: tuple[Adv1DialogueFactDefinition, ...]


@dataclass(frozen=True, slots=True)
class Adv1DialogueSocialTopicDefinition:
    topic: str
    topic_status: str
    persuade_check_required: bool


@dataclass(frozen=True, slots=True)
class Adv1DialogueSocialStageDefinition:
    plot_id: str
    plot_stage: str
    required_story_flags: list[str]
    topic_definitions: dict[str, Adv1DialogueSocialTopicDefinition]


@dataclass(frozen=True, slots=True)
class Adv1DialogueSocialNpcDefinition:
    npc_id: str
    baseline_stance: str
    baseline_cooperation: str
    guarded_dialogue_acts: list[str]
    stage_definitions: list[Adv1DialogueSocialStageDefinition]


@dataclass(frozen=True, slots=True)
class Adv1DialogueSocialState:
    npc_definitions: dict[str, Adv1DialogueSocialNpcDefinition]


@dataclass(frozen=True, slots=True)
class Adv1DialogueDossierSocialBaseline:
    relationship_to_player: str
    trust: int
    hostility: int
    fear: int
    respect: int
    willingness_to_cooperate: int
    current_conversation_stance: str


@dataclass(frozen=True, slots=True)
class Adv1DialogueDossierTopicGroup:
    group_id: str
    topics: tuple[str, ...]
    sensitivity: str
    taboo_topics: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Adv1DialogueDossierFactGroup:
    group_id: str
    fact_ids: tuple[str, ...]
    summary: str


@dataclass(frozen=True, slots=True)
class Adv1DialogueDossierPersonalityGuidance:
    speech_style: str
    banter_tolerance: str
    public_demeanor: str
    private_demeanor: str
    confrontation_style: str
    emotional_temperature: str
    directness_preference: str


@dataclass(frozen=True, slots=True)
class Adv1DialogueDossierDefinition:
    npc_id: str
    public_persona: str
    private_history_summary: str
    speaking_style: str
    relationship_context: str
    motivations: tuple[str, ...]
    personality_guidance: Adv1DialogueDossierPersonalityGuidance
    social_baseline: Adv1DialogueDossierSocialBaseline
    topic_groups: tuple[Adv1DialogueDossierTopicGroup, ...]
    revealable_fact_groups: tuple[Adv1DialogueDossierFactGroup, ...]


@dataclass(frozen=True, slots=True)
class Adv1DialogueDossierState:
    npc_definitions: dict[str, Adv1DialogueDossierDefinition]


def load_adv1_world_state(adventure_root: Path | None = None) -> WorldState:
    root = get_adventure_root() if adventure_root is None else Path(adventure_root)
    load_adv1_adventure_metadata(root)

    seed_data = load_adv1_world_state_seed_data(root)
    player_seed = load_adv1_player_seed_data(root)
    location_definitions = load_adv1_location_definitions(root)
    plot_thread_definitions = load_adv1_plot_thread_definitions(root)
    npc_definitions = load_adv1_npc_definitions(root)
    _validate_adv1_world_state_relations(
        player_seed=player_seed,
        location_definitions=location_definitions,
        npc_definitions=npc_definitions,
        plot_thread_definitions=plot_thread_definitions,
    )

    return WorldState(
        player=player_seed.player,
        npcs={npc_definition.id: _npc_from_definition(npc_definition) for npc_definition in npc_definitions},
        locations={location_definition.id: _location_from_definition(location_definition) for location_definition in location_definitions},
        plots={plot_definition.id: _plot_from_definition(plot_definition) for plot_definition in plot_thread_definitions},
        current_time=seed_data.current_time,
    )


def load_adv1_adventure_metadata(adventure_root: Path | None = None) -> Adv1AdventureMetadata:
    root = get_adventure_root() if adventure_root is None else Path(adventure_root)
    data = _read_json(root / "config" / "adventure.json")
    _validate_adventure_metadata(data)
    return Adv1AdventureMetadata(
        id=_require_str(data, "id"),
        name=_require_str(data, "name"),
        description=_require_str(data, "description"),
        starting_world_state_source=_require_str(data, "starting_world_state_source"),
    )


def load_adv1_player_seed_data(adventure_root: Path | None = None) -> Adv1PlayerSeedData:
    root = get_adventure_root() if adventure_root is None else Path(adventure_root)
    player_data = _read_json(root / "world" / "player.json")

    return Adv1PlayerSeedData(player=_player_from_dict(player_data))


def load_adv1_world_state_seed_data(adventure_root: Path | None = None) -> Adv1WorldSeedData:
    root = get_adventure_root() if adventure_root is None else Path(adventure_root)
    world_state_data = _read_json(root / "world" / "world_state.json")

    current_time = _require_iso_datetime(_require_str(world_state_data, "current_time"))
    return Adv1WorldSeedData(current_time=current_time)


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


def load_adv1_plot_outcome_definitions(adventure_root: Path | None = None) -> list[Adv1PlotOutcomeDefinition]:
    root = get_adventure_root() if adventure_root is None else Path(adventure_root)
    data = _read_json(root / "plots" / "plot_outcomes.json")
    outcome_entries = data.get("plots")
    if not isinstance(outcome_entries, list):
        raise AdventureContentError("Adventure field 'plots' must be a JSON array.")

    definitions: list[Adv1PlotOutcomeDefinition] = []
    for outcome_data in outcome_entries:
        if not isinstance(outcome_data, dict):
            raise AdventureContentError("Adventure plot outcome entries must be JSON objects.")
        definitions.append(_plot_outcome_definition_from_dict(outcome_data))
    return definitions


def load_adv1_dialogue_hook_definitions(adventure_root: Path | None = None) -> list[Adv1DialogueHookDefinition]:
    root = get_adventure_root() if adventure_root is None else Path(adventure_root)
    data = _read_json(root / "npcs" / "dialogue_hooks.json")
    hook_entries = data.get("dialogue_hooks")
    if not isinstance(hook_entries, list):
        raise AdventureContentError("Adventure field 'dialogue_hooks' must be a JSON array.")

    definitions: list[Adv1DialogueHookDefinition] = []
    for hook_data in hook_entries:
        if not isinstance(hook_data, dict):
            raise AdventureContentError("Adventure dialogue hook entries must be JSON objects.")
        definitions.append(_dialogue_hook_definition_from_dict(hook_data))
    return definitions


def load_adv1_dialogue_fact_definitions(adventure_root: Path | None = None) -> Adv1DialogueFactState:
    root = get_adventure_root() if adventure_root is None else Path(adventure_root)
    data = _read_json(root / "npcs" / "dialogue_facts.json")
    fact_entries = data.get("facts")
    if not isinstance(fact_entries, list):
        raise AdventureContentError("Adventure field 'facts' must be a JSON array.")

    definitions: list[Adv1DialogueFactDefinition] = []
    seen_fact_ids: set[str] = set()
    for fact_data in fact_entries:
        if not isinstance(fact_data, dict):
            raise AdventureContentError("Adventure dialogue fact entries must be JSON objects.")
        definition = _dialogue_fact_definition_from_dict(fact_data)
        if definition.fact_id in seen_fact_ids:
            raise AdventureContentError(f"Adventure dialogue facts must not duplicate fact_id '{definition.fact_id}'.")
        seen_fact_ids.add(definition.fact_id)
        definitions.append(definition)

    return Adv1DialogueFactState(fact_definitions=tuple(definitions))


def load_adv1_dialogue_social_state(adventure_root: Path | None = None) -> Adv1DialogueSocialState:
    root = get_adventure_root() if adventure_root is None else Path(adventure_root)
    data = _read_json(root / "npcs" / "social_state.json")
    npc_entries = data.get("npcs")
    if not isinstance(npc_entries, list):
        raise AdventureContentError("Adventure field 'npcs' must be a JSON array.")

    definitions: dict[str, Adv1DialogueSocialNpcDefinition] = {}
    for npc_data in npc_entries:
        if not isinstance(npc_data, dict):
            raise AdventureContentError("Adventure NPC social-state entries must be JSON objects.")
        definition = _dialogue_social_npc_definition_from_dict(npc_data)
        if definition.npc_id in definitions:
            raise AdventureContentError(f"Adventure NPC social-state entries must not duplicate npc_id '{definition.npc_id}'.")
        definitions[definition.npc_id] = definition

    return Adv1DialogueSocialState(npc_definitions=definitions)


def load_adv1_dialogue_dossiers(adventure_root: Path | None = None) -> Adv1DialogueDossierState:
    root = get_adventure_root() if adventure_root is None else Path(adventure_root)
    data = _read_json(root / "npcs" / "dialogue_dossiers.json")
    dossier_entries = data.get("dialogue_dossiers")
    if not isinstance(dossier_entries, list):
        raise AdventureContentError("Adventure field 'dialogue_dossiers' must be a JSON array.")

    definitions: dict[str, Adv1DialogueDossierDefinition] = {}
    for dossier_data in dossier_entries:
        if not isinstance(dossier_data, dict):
            raise AdventureContentError("Adventure dialogue dossier entries must be JSON objects.")
        definition = _dialogue_dossier_definition_from_dict(dossier_data)
        if definition.npc_id in definitions:
            raise AdventureContentError(f"Adventure dialogue dossiers must not duplicate npc_id '{definition.npc_id}'.")
        definitions[definition.npc_id] = definition

    return Adv1DialogueDossierState(npc_definitions=definitions)


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
    talk_rule = _require_mapping(data, "talk")

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
        talk_from_stage=_require_str(talk_rule, "from_stage"),
        talk_npc_id=_require_str(talk_rule, "npc_id"),
        talk_location_id=_require_str(talk_rule, "location_id"),
        talk_minimum_trust_level=_require_int(talk_rule, "minimum_trust_level"),
        talk_required_story_flag=_require_str(talk_rule, "required_story_flag"),
        talk_to_stage=_require_str(talk_rule, "to_stage"),
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


def _validate_adv1_world_state_relations(
    *,
    player_seed: Adv1PlayerSeedData,
    location_definitions: list[Adv1LocationDefinition],
    npc_definitions: list[Adv1NpcDefinition],
    plot_thread_definitions: list[Adv1PlotThreadDefinition],
) -> None:
    location_ids = {definition.id for definition in location_definitions}
    plot_ids = {definition.id for definition in plot_thread_definitions}

    player_location_id = player_seed.player.location_id
    if player_location_id is not None and player_location_id not in location_ids:
        raise AdventureContentError(
            f"Player starting location '{player_location_id}' does not exist in ADV1 locations."
        )

    for npc_definition in npc_definitions:
        if npc_definition.starting_location_id not in location_ids:
            raise AdventureContentError(
                f"NPC '{npc_definition.id}' starting location '{npc_definition.starting_location_id}' does not exist in ADV1 locations."
            )

    for location_definition in location_definitions:
        for connected_location_id in location_definition.connected_locations:
            if connected_location_id not in location_ids:
                raise AdventureContentError(
                    f"Location '{location_definition.id}' references missing connected location '{connected_location_id}'."
                )
        for destination_id in location_definition.travel_time:
            if destination_id not in location_ids:
                raise AdventureContentError(
                    f"Location '{location_definition.id}' defines travel time to missing location '{destination_id}'."
                )

    if "plot_1" not in plot_ids:
        raise AdventureContentError("ADV1 must define plot 'plot_1' to construct the playable startup world.")


def _require_iso_datetime(value: str) -> str:
    try:
        datetime.fromisoformat(value)
    except ValueError as exc:
        raise AdventureContentError(f"Adventure field 'current_time' must be a valid ISO datetime, found '{value}'.") from exc
    return value


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
    attitude_to_player = _require_str(data, "attitude_to_player")
    trust_level = _require_int(data, "trust_level") if "trust_level" in data else 0
    return NPC(
        id=_require_str(data, "id"),
        name=_require_str(data, "name"),
        role=_require_str(data, "role"),
        location_id=data.get("location_id"),
        attitude_to_player=attitude_to_player,
        trust_level=trust_level,
        goals=_require_string_list(data, "goals"),
        investigation_hint=_require_str(data, "investigation_hint"),
        schedule=dict(data.get("schedule", {})),
        traits=dict(data.get("traits", {})),
        dialogue_profile=_dialogue_profile_from_dict(data.get("dialogue_profile")),
        social_state=NPCSocialState(
            relationship_to_player=attitude_to_player,
            trust=trust_level,
        ),
    )


def _npc_definition_from_dict(data: dict[str, Any]) -> Adv1NpcDefinition:
    attitude_to_player = _require_str(data, "attitude_to_player")
    trust_level = _require_int(data, "trust_level")
    social_state = _social_state_from_dict(data.get("social_state"), attitude_to_player, trust_level)
    return Adv1NpcDefinition(
        id=_require_str(data, "id"),
        name=_require_str(data, "name"),
        role=_require_str(data, "role"),
        starting_location_id=_require_str(data, "starting_location_id"),
        attitude_to_player=attitude_to_player,
        trust_level=trust_level,
        previous_interactions_summary=_require_optional_profile_str(data, "previous_interactions_summary"),
        social_state=social_state,
        goals=_require_string_list(data, "goals"),
        investigation_hint=_require_str(data, "investigation_hint"),
        traits=_require_string_mapping(data, "traits"),
        schedule=_require_string_mapping(data, "schedule"),
        dialogue_profile=_dialogue_profile_from_dict(data.get("dialogue_profile")),
    )


def _dialogue_social_npc_definition_from_dict(data: dict[str, Any]) -> Adv1DialogueSocialNpcDefinition:
    stage_entries = data.get("stage_definitions")
    if not isinstance(stage_entries, list) or not stage_entries:
        raise AdventureContentError("Adventure field 'stage_definitions' must be a non-empty JSON array.")

    stage_definitions: list[Adv1DialogueSocialStageDefinition] = []
    for stage_data in stage_entries:
        if not isinstance(stage_data, dict):
            raise AdventureContentError("Adventure stage definitions must be JSON objects.")
        stage_definitions.append(_dialogue_social_stage_definition_from_dict(stage_data))

    return Adv1DialogueSocialNpcDefinition(
        npc_id=_require_str(data, "npc_id"),
        baseline_stance=_require_str(data, "baseline_stance"),
        baseline_cooperation=_require_str(data, "baseline_cooperation"),
        guarded_dialogue_acts=_require_string_list(data, "guarded_dialogue_acts"),
        stage_definitions=stage_definitions,
    )


def _dialogue_social_stage_definition_from_dict(data: dict[str, Any]) -> Adv1DialogueSocialStageDefinition:
    topic_entries = data.get("topic_definitions")
    if not isinstance(topic_entries, list) or not topic_entries:
        raise AdventureContentError("Adventure field 'topic_definitions' must be a non-empty JSON array.")

    topic_definitions: dict[str, Adv1DialogueSocialTopicDefinition] = {}
    for topic_data in topic_entries:
        if not isinstance(topic_data, dict):
            raise AdventureContentError("Adventure topic definitions must be JSON objects.")
        topic_definition = _dialogue_social_topic_definition_from_dict(topic_data)
        if topic_definition.topic in topic_definitions:
            raise AdventureContentError(f"Adventure topic definitions must not duplicate topic '{topic_definition.topic}'.")
        topic_definitions[topic_definition.topic] = topic_definition

    return Adv1DialogueSocialStageDefinition(
        plot_id=_require_str(data, "plot_id"),
        plot_stage=_require_str(data, "plot_stage"),
        required_story_flags=_require_string_list(data, "required_story_flags"),
        topic_definitions=topic_definitions,
    )


def _dialogue_social_topic_definition_from_dict(data: dict[str, Any]) -> Adv1DialogueSocialTopicDefinition:
    topic_status = _require_str(data, "topic_status")
    if topic_status not in {"productive", "available", "refused"}:
        raise AdventureContentError(
            "Adventure field 'topic_status' must be one of 'productive', 'available', or 'refused'."
        )
    return Adv1DialogueSocialTopicDefinition(
        topic=_require_str(data, "topic"),
        topic_status=topic_status,
        persuade_check_required=_require_bool(data, "persuade_check_required"),
    )


def _dialogue_dossier_definition_from_dict(data: dict[str, Any]) -> Adv1DialogueDossierDefinition:
    topic_group_entries = data.get("topic_groups")
    if not isinstance(topic_group_entries, list):
        raise AdventureContentError("Adventure field 'topic_groups' must be a JSON array.")

    topic_groups: list[Adv1DialogueDossierTopicGroup] = []
    seen_topic_group_ids: set[str] = set()
    for topic_group_data in topic_group_entries:
        if not isinstance(topic_group_data, dict):
            raise AdventureContentError("Adventure topic group entries must be JSON objects.")
        topic_group = _dialogue_dossier_topic_group_from_dict(topic_group_data)
        if topic_group.group_id in seen_topic_group_ids:
            raise AdventureContentError(
                f"Adventure topic groups must not duplicate group_id '{topic_group.group_id}'."
            )
        seen_topic_group_ids.add(topic_group.group_id)
        topic_groups.append(topic_group)

    revealable_fact_group_entries = data.get("revealable_fact_groups")
    if not isinstance(revealable_fact_group_entries, list):
        raise AdventureContentError("Adventure field 'revealable_fact_groups' must be a JSON array.")

    revealable_fact_groups: list[Adv1DialogueDossierFactGroup] = []
    seen_fact_group_ids: set[str] = set()
    for fact_group_data in revealable_fact_group_entries:
        if not isinstance(fact_group_data, dict):
            raise AdventureContentError("Adventure revealable fact group entries must be JSON objects.")
        fact_group = _dialogue_dossier_fact_group_from_dict(fact_group_data)
        if fact_group.group_id in seen_fact_group_ids:
            raise AdventureContentError(
                f"Adventure revealable fact groups must not duplicate group_id '{fact_group.group_id}'."
            )
        seen_fact_group_ids.add(fact_group.group_id)
        revealable_fact_groups.append(fact_group)

    return Adv1DialogueDossierDefinition(
        npc_id=_require_str(data, "npc_id"),
        public_persona=_require_str(data, "public_persona"),
        private_history_summary=_require_str(data, "private_history_summary"),
        speaking_style=_require_str(data, "speaking_style"),
        relationship_context=_require_str(data, "relationship_context"),
        motivations=tuple(_require_string_list(data, "motivations")),
        personality_guidance=_dialogue_dossier_personality_guidance_from_dict(_require_mapping(data, "personality_guidance")),
        social_baseline=_dialogue_dossier_social_baseline_from_dict(_require_mapping(data, "social_baseline")),
        topic_groups=tuple(topic_groups),
        revealable_fact_groups=tuple(revealable_fact_groups),
    )


def _dialogue_dossier_personality_guidance_from_dict(data: dict[str, Any]) -> Adv1DialogueDossierPersonalityGuidance:
    return Adv1DialogueDossierPersonalityGuidance(
        speech_style=_require_str(data, "speech_style"),
        banter_tolerance=_require_str(data, "banter_tolerance"),
        public_demeanor=_require_str(data, "public_demeanor"),
        private_demeanor=_require_str(data, "private_demeanor"),
        confrontation_style=_require_str(data, "confrontation_style"),
        emotional_temperature=_require_str(data, "emotional_temperature"),
        directness_preference=_require_str(data, "directness_preference"),
    )


def _dialogue_dossier_social_baseline_from_dict(data: dict[str, Any]) -> Adv1DialogueDossierSocialBaseline:
    return Adv1DialogueDossierSocialBaseline(
        relationship_to_player=_require_str(data, "relationship_to_player"),
        trust=_require_int(data, "trust"),
        hostility=_require_int(data, "hostility"),
        fear=_require_int(data, "fear"),
        respect=_require_int(data, "respect"),
        willingness_to_cooperate=_require_int(data, "willingness_to_cooperate"),
        current_conversation_stance=_require_str(data, "current_conversation_stance"),
    )


def _dialogue_dossier_topic_group_from_dict(data: dict[str, Any]) -> Adv1DialogueDossierTopicGroup:
    return Adv1DialogueDossierTopicGroup(
        group_id=_require_str(data, "group_id"),
        topics=tuple(_require_string_list(data, "topics")),
        sensitivity=_require_str(data, "sensitivity"),
        taboo_topics=tuple(_require_string_list(data, "taboo_topics")),
    )


def _dialogue_dossier_fact_group_from_dict(data: dict[str, Any]) -> Adv1DialogueDossierFactGroup:
    return Adv1DialogueDossierFactGroup(
        group_id=_require_str(data, "group_id"),
        fact_ids=tuple(_require_string_list(data, "fact_ids")),
        summary=_require_str(data, "summary"),
    )


def _npc_from_definition(definition: Adv1NpcDefinition) -> NPC:
    return NPC(
        id=definition.id,
        name=definition.name,
        role=definition.role,
        location_id=definition.starting_location_id,
        attitude_to_player=definition.attitude_to_player,
        trust_level=definition.social_state.trust,
        previous_interactions_summary=definition.previous_interactions_summary,
        goals=list(definition.goals),
        investigation_hint=definition.investigation_hint,
        schedule=dict(definition.schedule),
        traits=dict(definition.traits),
        dialogue_profile=definition.dialogue_profile,
        social_state=definition.social_state,
    )


def _dialogue_profile_from_dict(data: Any) -> NPCDialogueProfile:
    if data is None:
        return NPCDialogueProfile()
    if not isinstance(data, dict):
        raise AdventureContentError("Adventure field 'dialogue_profile' must be a JSON object.")
    return NPCDialogueProfile(
        background_summary=_require_optional_profile_str(data, "background_summary"),
        public_persona=_require_optional_profile_str(data, "public_persona"),
        private_history_summary=_require_optional_profile_str(data, "private_history_summary"),
        motivations=_require_optional_string_list(data, "motivations"),
        speaking_style=_require_optional_profile_str(data, "speaking_style"),
        relationship_context=_require_optional_profile_str(data, "relationship_context"),
    )


def _social_state_from_dict(data: Any, attitude_to_player: str, trust_level: int) -> NPCSocialState:
    if data is None:
        return NPCSocialState(
            relationship_to_player=attitude_to_player,
            trust=trust_level,
        )
    if not isinstance(data, dict):
        raise AdventureContentError("Adventure field 'social_state' must be a JSON object.")

    topic_sensitivity_raw = data.get("topic_sensitivity", {})
    if not isinstance(topic_sensitivity_raw, dict):
        raise AdventureContentError("Adventure field 'topic_sensitivity' must be a JSON object.")
    topic_sensitivity: dict[str, TopicSensitivity] = {}
    for topic, sensitivity in topic_sensitivity_raw.items():
        if not isinstance(topic, str) or not topic:
            raise AdventureContentError("Adventure field 'topic_sensitivity' must use non-empty string keys.")
        if not isinstance(sensitivity, str):
            raise AdventureContentError("Adventure field 'topic_sensitivity' must use string values.")
        topic_sensitivity[topic] = TopicSensitivity(sensitivity)

    stance_value = data.get("current_conversation_stance", ConversationStance.NEUTRAL.value)
    if not isinstance(stance_value, str):
        raise AdventureContentError("Adventure field 'current_conversation_stance' must be a string.")

    return NPCSocialState(
        relationship_to_player=str(data.get("relationship_to_player", attitude_to_player)),
        trust=int(data.get("trust", trust_level)) if isinstance(data.get("trust", trust_level), int) else trust_level,
        hostility=int(data.get("hostility", 0)) if isinstance(data.get("hostility", 0), int) else 0,
        fear=int(data.get("fear", 0)) if isinstance(data.get("fear", 0), int) else 0,
        respect=int(data.get("respect", 0)) if isinstance(data.get("respect", 0), int) else 0,
        willingness_to_cooperate=int(data.get("willingness_to_cooperate", 0)) if isinstance(data.get("willingness_to_cooperate", 0), int) else 0,
        current_conversation_stance=ConversationStance(stance_value),
        topic_sensitivity=topic_sensitivity,
    )


def _location_definition_from_dict(data: dict[str, Any]) -> Adv1LocationDefinition:
    return Adv1LocationDefinition(
        id=_require_str(data, "id"),
        name=_require_str(data, "name"),
        type=_require_str(data, "type"),
        connected_locations=_require_string_list(data, "connected_locations"),
        travel_time=_require_int_mapping(data, "travel_time"),
        danger_level=_require_int(data, "danger_level"),
        scene_hook=_require_str(data, "scene_hook"),
        notable_features=_require_string_list(data, "notable_features"),
        flavor_tags=_require_string_list(data, "flavor_tags"),
    )


def _location_from_definition(definition: Adv1LocationDefinition) -> Location:
    return Location(
        id=definition.id,
        name=definition.name,
        type=definition.type,
        connected_locations=list(definition.connected_locations),
        travel_time=dict(definition.travel_time),
        danger_level=definition.danger_level,
        scene_hook=definition.scene_hook,
        notable_features=list(definition.notable_features),
        flavor_tags=list(definition.flavor_tags),
    )


def _location_from_dict(data: dict[str, Any]) -> Location:
    return Location(
        id=_require_str(data, "id"),
        name=_require_str(data, "name"),
        type=_require_str(data, "type"),
        connected_locations=_require_string_list(data, "connected_locations"),
        travel_time=_require_int_mapping(data, "travel_time"),
        danger_level=_require_int(data, "danger_level"),
        scene_hook=str(data.get("scene_hook", "")),
        notable_features=list(data.get("notable_features", [])),
        flavor_tags=list(data.get("flavor_tags", [])),
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


def _plot_outcome_definition_from_dict(data: dict[str, Any]) -> Adv1PlotOutcomeDefinition:
    return Adv1PlotOutcomeDefinition(
        id=_require_str(data, "id"),
        name=_require_str(data, "name"),
        resolved_event_text=_require_str(data, "resolved_event_text"),
        learned_outcome=_require_str(data, "learned_outcome"),
        closing_beat=_require_str(data, "closing_beat"),
        trust_adjustments=_require_int_mapping(data, "trust_adjustments"),
    )


def _dialogue_hook_definition_from_dict(data: dict[str, Any]) -> Adv1DialogueHookDefinition:
    return Adv1DialogueHookDefinition(
        hook_id=_require_str(data, "hook_id"),
        npc_id=_require_str(data, "npc_id"),
        required_plot_id=_require_str(data, "required_plot_id"),
        required_plot_stage=_require_str(data, "required_plot_stage"),
        minimum_trust_level=_require_int(data, "minimum_trust_level"),
        trust_delta=_require_int(data, "trust_delta"),
        repeatable=_require_bool(data, "repeatable"),
        required_dialogue_acts=_require_string_list(data, "required_dialogue_acts") if "required_dialogue_acts" in data else [],
        story_flags_to_add=_require_string_list(data, "story_flags_to_add") if "story_flags_to_add" in data else [],
    )


def _dialogue_fact_definition_from_dict(data: dict[str, Any]) -> Adv1DialogueFactDefinition:
    kind = _require_str(data, "kind")
    if kind not in {"lead", "background", "boundary", "redirect", "refusal_basis"}:
        raise AdventureContentError(
            "Adventure field 'kind' must be one of 'lead', 'background', 'boundary', 'redirect', or 'refusal_basis'."
        )
    requires_check_success = data.get("requires_check_success")
    if requires_check_success is not None and not isinstance(requires_check_success, bool):
        raise AdventureContentError("Adventure field 'requires_check_success' must be a boolean when present.")
    return Adv1DialogueFactDefinition(
        fact_id=_require_str(data, "fact_id"),
        npc_id=_require_str(data, "npc_id"),
        plot_id=_optional_str(data.get("plot_id"), "plot_id"),
        subtopic=_optional_str(data.get("subtopic"), "subtopic"),
        summary=_require_str(data, "summary"),
        kind=kind,
        required_plot_stages=tuple(_require_optional_string_list(data, "required_plot_stages")),
        required_story_flags=tuple(_require_optional_string_list(data, "required_story_flags")),
        allowed_outcome_kinds=tuple(_require_optional_string_list(data, "allowed_outcome_kinds")),
        allowed_topic_results=tuple(_require_optional_string_list(data, "allowed_topic_results")),
        requires_check_success=requires_check_success,
        required_dialogue_domains=tuple(_require_optional_string_list(data, "required_dialogue_domains")),
        required_dialogue_acts=tuple(_require_optional_string_list(data, "required_dialogue_acts")),
        required_keywords=tuple(_require_optional_string_list(data, "required_keywords")),
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


def _require_optional_string_list(data: dict[str, Any], field_name: str) -> list[str]:
    if field_name not in data:
        return []
    return _require_string_list(data, field_name)


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


def _require_optional_profile_str(data: dict[str, Any], field_name: str) -> str:
    value = data.get(field_name, "")
    if not isinstance(value, str):
        raise AdventureContentError(f"Adventure field '{field_name}' must be a string.")
    return value.strip()


def _optional_str(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise AdventureContentError(f"Adventure field '{field_name}' must be a string when present.")
    normalized = value.strip()
    return normalized or None
