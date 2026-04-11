"""Core data structures for the Vampire: The Masquerade storyteller prototype."""

from .config import AppConfig, load_config
from .adventure_loader import (
    AdventureContentError,
    Adv1NpcDefinition,
    Adv1LocationDefinition,
    Adv1PlotThreadDefinition,
    Adv1PlotOutcomeDefinition,
    Adv1DialogueHookDefinition,
    Adv1PlayerSeedData,
    Adv1WorldSeedData,
    PlotInvestigationRules,
    PlotProgressionRules,
    load_adv1_location_definitions,
    load_adv1_npc_definitions,
    load_adv1_plot_thread_definitions,
    load_adv1_plot_outcome_definitions,
    load_adv1_dialogue_hook_definitions,
    load_adv1_player_seed_data,
    load_adv1_plot_investigation_rules,
    load_adv1_plot_progression_rules,
    load_adv1_world_state,
    load_adv1_world_state_seed_data,
)
from .models import EventLogEntry, Location, NPC, Player, PlotThread
from .adjudication_engine import AdjudicationDecision, adjudicate_command
from .command_dispatcher import execute_command
from .command_models import Command, HelpCommand, InvestigateCommand, LoadCommand, LookCommand, MoveCommand, QuitCommand, SaveCommand, StatusCommand, TalkCommand, WaitCommand
from .command_result import CommandResult
from .command_parser import parse_command
from .context_builder import build_scene_snapshot, snapshot_to_prompt_text
from .game_session import GameSession
from .consequence_engine import apply_consequences
from .dice_engine import DiceRollResult, roll_dice
from .data_paths import (
    ADVENTURE_ID,
    ADVENTURE_ROOT,
    ensure_adventure_directories,
    get_adventure_config_path,
    get_adventure_locations_seed_path,
    get_adventure_metadata_path,
    get_adventure_npcs_seed_path,
    get_adventure_notes_path,
    get_adventure_plot_threads_seed_path,
    get_adventure_player_seed_path,
    get_adventure_plots_seed_path,
    get_adventure_plot_progression_path,
    get_adventure_plot_resolution_path,
    get_adventure_root,
    get_adventure_world_state_seed_path,
    get_adventure_world_path,
    get_default_save_path,
)
from .npc_engine import get_time_band, update_npcs_for_current_time
from .narrative_provider import DeterministicSceneNarrativeProvider, SceneNarrativeProvider
from .openai_narrative_provider import OpenAISceneNarrativeProvider
from .plot_engine import advance_plots
from .serialization import load_world_state, save_world_state
from .exceptions import CommandParseError, ContextBuildError, InvalidLocationError, MovementError, WorldStateError
from .hunger_engine import apply_hunger_for_elapsed_time
from .map_engine import move_player
from .scene_models import SceneNPC, SceneSnapshot
from .sample_world import build_sample_world
from .text_renderers import render_help_text, render_scene_text, render_status_text
from .time_engine import advance_time, format_time, parse_time
from .actions import wait_action
from .world_state import WorldState

__all__ = [
    "AppConfig",
    "AdventureContentError",
    "Adv1LocationDefinition",
    "Adv1NpcDefinition",
    "Adv1PlotThreadDefinition",
    "Adv1PlotOutcomeDefinition",
    "Adv1DialogueHookDefinition",
    "Adv1PlayerSeedData",
    "Adv1WorldSeedData",
    "PlotInvestigationRules",
    "PlotProgressionRules",
    "AdjudicationDecision",
    "EventLogEntry",
    "Command",
    "CommandParseError",
    "CommandResult",
    "ContextBuildError",
    "DiceRollResult",
    "apply_consequences",
    "DeterministicSceneNarrativeProvider",
    "ADVENTURE_ID",
    "ADVENTURE_ROOT",
    "get_adventure_metadata_path",
    "get_adventure_world_path",
    "get_adventure_player_seed_path",
    "get_adventure_locations_seed_path",
    "get_adventure_npcs_seed_path",
    "get_adventure_plots_seed_path",
    "get_adventure_plot_progression_path",
    "get_adventure_plot_resolution_path",
    "GameSession",
    "build_sample_world",
    "load_adv1_location_definitions",
    "load_adv1_npc_definitions",
    "load_adv1_plot_thread_definitions",
    "load_adv1_plot_outcome_definitions",
    "load_adv1_dialogue_hook_definitions",
    "load_adv1_player_seed_data",
    "advance_plots",
    "get_time_band",
    "ensure_adventure_directories",
    "HelpCommand",
    "InvalidLocationError",
    "Location",
    "LookCommand",
    "MovementError",
    "NPC",
    "InvestigateCommand",
    "LoadCommand",
    "Player",
    "MoveCommand",
    "TalkCommand",
    "OpenAISceneNarrativeProvider",
    "SceneNarrativeProvider",
    "PlotThread",
    "QuitCommand",
    "SaveCommand",
    "SceneNPC",
    "SceneSnapshot",
    "StatusCommand",
    "WorldStateError",
    "WorldState",
    "load_adv1_world_state",
    "load_adv1_world_state_seed_data",
    "load_adv1_plot_progression_rules",
    "load_adv1_plot_investigation_rules",
    "get_adventure_root",
    "get_adventure_config_path",
    "get_adventure_notes_path",
    "get_adventure_plot_threads_seed_path",
    "get_adventure_world_state_seed_path",
    "get_default_save_path",
    "advance_time",
    "apply_hunger_for_elapsed_time",
    "build_scene_snapshot",
    "execute_command",
    "format_time",
    "load_config",
    "load_world_state",
    "build_scene_provider",
    "adjudicate_command",
    "update_npcs_for_current_time",
    "parse_command",
    "move_player",
    "parse_time",
    "save_world_state",
    "roll_dice",
    "render_help_text",
    "render_scene_text",
    "render_status_text",
    "snapshot_to_prompt_text",
    "WaitCommand",
    "run_cli",
    "run_gui",
    "wait_action",
]


def build_scene_provider(config: AppConfig | None = None) -> tuple[SceneNarrativeProvider, str | None]:
    from .cli import build_scene_provider as _build_scene_provider

    return _build_scene_provider(config)


def run_cli() -> None:
    from .cli import run_cli as _run_cli

    _run_cli()


def run_gui() -> None:
    from .gui_app import run_gui as _run_gui

    _run_gui()
