from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from .adjudication_engine import AdjudicationDecision, adjudicate_command
from .command_dispatcher import execute_command
from .command_models import Command, InvestigateCommand, LoadCommand, MoveCommand, SaveCommand, TalkCommand, WaitCommand
from .command_parser import parse_command
from .command_result import CommandResult
from .consequence_engine import apply_consequences
from .dice_engine import roll_dice
from .data_paths import ensure_adventure_directories, get_default_save_path
from .command_models import ConversationStance
from .adventure_loader import load_adv1_plot_investigation_rules
from .conversation_context import ConversationContext
from .input_interpreter import InputInterpreter, InterpretedInput
from .models import EventLogEntry
from .npc_engine import update_npcs_for_current_time
from .narrative_provider import DeterministicSceneNarrativeProvider, SceneNarrativeProvider
from .plot_engine import advance_plots
from .sample_world import build_sample_world
from .serialization import load_world_state, save_world_state
from .world_state import WorldState


class GameSession:
    def __init__(
        self,
        world_state: WorldState | None = None,
        scene_provider: SceneNarrativeProvider | None = None,
        save_path: str | Path | None = None,
    ) -> None:
        self._world_state = world_state if world_state is not None else build_sample_world()
        self._scene_provider = scene_provider if scene_provider is not None else DeterministicSceneNarrativeProvider()
        self._fallback_scene_provider = DeterministicSceneNarrativeProvider()
        self._input_interpreter = InputInterpreter()
        self._last_interpreted_input: InterpretedInput | None = None
        self._conversation_context = ConversationContext()
        self._save_path = Path(save_path) if save_path is not None else get_default_save_path()

    def get_startup_text(self) -> str:
        return self._render_scene_text()

    def process_input(self, raw_input: str) -> CommandResult:
        # Phase 1: interpret freeform input against the current world and session context.
        interpretation = self._interpret_input(raw_input)
        self._last_interpreted_input = interpretation
        if interpretation.no_active_conversation:
            return CommandResult(output_text="There is no active conversation to continue.")

        # Phase 2: normalize to the canonical structured command.
        command = self._normalize_command(raw_input, interpretation)

        # Phase 3: handle session-level commands that do not enter the world pipeline.
        session_result = self._handle_session_command(command)
        if session_result is not None:
            return session_result

        # Phase 4: adjudicate the command against the current world state.
        adjudication = self._adjudicate_command(command)
        if isinstance(adjudication, CommandResult):
            return adjudication

        # Phase 5: execute the canonical command.
        result = self._execute_command(command)
        if result.should_quit:
            return result

        # Phase 6: update session-local dialogue state and fold in any talk-side plot progress.
        result = self._apply_talk_after_effects(command, result)

        # Phase 7: apply deterministic world consequences.
        result = self._apply_consequences_phase(command, result, adjudication)

        # Phase 8: advance NPC schedules after world time has settled.
        result = self._apply_npc_updates_phase(command, result)

        # Phase 9: advance authored plot state using the final post-action world state.
        result = self._apply_plot_progression_phase(command, result)

        # Phase 10: render the final response for the player.
        return self._render_response(command, result)

    def get_world_state(self) -> WorldState:
        return self._world_state

    def get_last_interpreted_input(self) -> InterpretedInput | None:
        return self._last_interpreted_input

    def get_conversation_focus_npc_id(self) -> str | None:
        return self._conversation_context.focus_npc_id

    def get_conversation_stance(self) -> ConversationStance:
        return self._conversation_context.stance

    def _interpret_input(self, raw_input: str) -> InterpretedInput:
        self._conversation_context.sync_with_world(self._world_state)
        return self._input_interpreter.interpret(raw_input, self._world_state, self._conversation_context.focus_npc_id)

    def _normalize_command(self, raw_input: str, interpretation: InterpretedInput) -> Command:
        command_input = interpretation.canonical_command if not interpretation.fallback_to_parser else raw_input
        command = parse_command(command_input)
        if isinstance(command, TalkCommand) and self._conversation_context.focus_npc_id not in (None, command.npc_id):
            self._conversation_context.clear()
        if isinstance(command, TalkCommand) and interpretation.dialogue_metadata is not None:
            command = replace(
                command,
                dialogue_metadata=interpretation.dialogue_metadata,
                conversation_stance=self._conversation_context.stance,
            )
        elif isinstance(command, TalkCommand):
            command = replace(command, conversation_stance=self._conversation_context.stance)
        return command

    def _handle_session_command(self, command: Command) -> CommandResult | None:
        if isinstance(command, SaveCommand):
            ensure_adventure_directories()
            save_world_state(self._world_state, self._save_path)
            return CommandResult(output_text=f"Game saved to {self._save_path.as_posix()}.")

        if isinstance(command, LoadCommand):
            self._conversation_context.clear()
            if not self._save_path.exists():
                return CommandResult(output_text=f"No save file found at {self._save_path.as_posix()}.")
            self._world_state = load_world_state(self._save_path)
            return CommandResult(output_text=self._render_scene_text(), render_scene=True)

        return None

    def _adjudicate_command(self, command: Command) -> AdjudicationDecision | CommandResult:
        adjudication = adjudicate_command(self._world_state, command)
        if isinstance(command, InvestigateCommand) and not adjudication.requires_roll:
            return CommandResult(
                output_text=adjudication.blocked_feedback or "Investigate is blocked.",
            )
        return adjudication

    def _execute_command(self, command: Command) -> CommandResult:
        return execute_command(self._world_state, command)

    def _apply_talk_after_effects(self, command: Command, result: CommandResult) -> CommandResult:
        if not isinstance(command, TalkCommand):
            return result

        if result.conversation_focus_npc_id is not None:
            self._conversation_context.replace_focus(result.conversation_focus_npc_id)
            self._conversation_context.stance = result.conversation_stance
        return result

    def _apply_consequences_phase(
        self,
        command: Command,
        result: CommandResult,
        adjudication: AdjudicationDecision,
    ) -> CommandResult:
        if not result.render_scene or not adjudication.requires_roll:
            return result

        roll_result = self._resolve_roll(command, adjudication)
        apply_consequences(self._world_state, command, roll_result=roll_result)
        return result

    def _resolve_roll(self, command: Command, adjudication: AdjudicationDecision):
        seed = self._derive_roll_seed(command)
        assert adjudication.roll_pool is not None
        assert adjudication.difficulty is not None
        plot_id = load_adv1_plot_investigation_rules().plot_id
        roll_result = roll_dice(adjudication.roll_pool, adjudication.difficulty, seed=seed)
        self._world_state.append_event(
            EventLogEntry(
                timestamp=self._world_state.current_time,
                description=(
                    f"Rolled {roll_result.pool} dice vs difficulty {roll_result.difficulty}: "
                    f"{roll_result.individual_rolls} -> {roll_result.successes} successes."
                ),
                involved_entities=[
                    self._world_state.player.id,
                    plot_id,
                    self._world_state.player.location_id or "",
                ],
            )
        )
        return roll_result

    def _apply_npc_updates_phase(self, command: Command, result: CommandResult) -> CommandResult:
        if not result.render_scene or not isinstance(command, (MoveCommand, WaitCommand)):
            return result

        self._conversation_context.clear()
        update_npcs_for_current_time(self._world_state)
        return result

    def _apply_plot_progression_phase(self, command: Command, result: CommandResult) -> CommandResult:
        if not (result.render_scene or isinstance(command, TalkCommand)):
            return result

        plot_messages = advance_plots(self._world_state, command)
        if not plot_messages or result.render_scene:
            return result

        return CommandResult(
            output_text="\n".join([result.output_text, *plot_messages]) if result.output_text else "\n".join(plot_messages),
            should_quit=result.should_quit,
            render_scene=result.render_scene,
            conversation_focus_npc_id=result.conversation_focus_npc_id,
            conversation_stance=result.conversation_stance,
        )

    def _render_response(self, command: Command, result: CommandResult) -> CommandResult:
        if not result.render_scene:
            return result

        if isinstance(command, InvestigateCommand):
            epilogue_text = self._build_resolution_epilogue()
            if epilogue_text:
                rendered_scene_text = self._render_scene_text()
                return CommandResult(
                    output_text=f"{epilogue_text}\n\n{rendered_scene_text}",
                    should_quit=result.should_quit,
                    render_scene=True,
                )

        return CommandResult(
            output_text=self._render_scene_text(),
            should_quit=result.should_quit,
            render_scene=True,
            conversation_focus_npc_id=result.conversation_focus_npc_id,
            conversation_stance=result.conversation_stance,
        )

    def _render_scene_text(self) -> str:
        try:
            return self._scene_provider.render_scene(self._world_state)
        except Exception:
            self._scene_provider = self._fallback_scene_provider
            return self._fallback_scene_provider.render_scene(self._world_state)

    def _derive_roll_seed(self, command: Command) -> str:
        command_name = command.__class__.__name__.removesuffix("Command").lower()
        player_id = self._world_state.player.id
        return f"{self._world_state.current_time}|{command_name}|{player_id}"

    def _build_resolution_epilogue(self) -> str:
        plot_id = load_adv1_plot_investigation_rules().plot_id
        plot = self._world_state.plots.get(plot_id)
        if plot is None or plot.active:
            return ""
        if not plot.resolution_summary or not plot.learned_outcome or not plot.closing_beat:
            return ""
        return "\n".join(
            [
                plot.resolution_summary,
                f"Learned: {plot.learned_outcome}",
                f"Closing beat: {plot.closing_beat}",
            ]
        )
