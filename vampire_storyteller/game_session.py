from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from .action_resolution import (
    ActionAdjudicationOutcome,
    ActionCheckOutcome,
    ActionConsequenceSummary,
    ActionResolutionTurn,
    NormalizationSource,
    NormalizedActionInput,
    adjudication_outcome_from_decision,
)
from .adjudication_engine import adjudicate_command
from .adventure_loader import load_adv1_plot_investigation_rules
from .command_dispatcher import execute_command
from .command_models import Command, ConversationStance, InvestigateCommand, LoadCommand, MoveCommand, SaveCommand, TalkCommand, WaitCommand
from .exceptions import CommandParseError
from .command_parser import parse_command
from .command_result import CommandResult
from .consequence_engine import apply_consequences
from .conversation_context import ConversationContext
from .data_paths import ensure_adventure_directories, get_default_save_path
from .dice_engine import resolve_deterministic_check
from .input_interpreter import InputInterpreter, InterpretedInput
from .models import EventLogEntry
from .narrative_provider import DeterministicSceneNarrativeProvider, SceneNarrativeProvider
from .npc_engine import update_npcs_for_current_time
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
        self._last_normalized_action: NormalizedActionInput | None = None
        self._last_action_resolution: ActionResolutionTurn | None = None
        self._conversation_context = ConversationContext()
        self._save_path = Path(save_path) if save_path is not None else get_default_save_path()

    def get_startup_text(self) -> str:
        return self._render_scene_text()

    def process_input(self, raw_input: str) -> CommandResult:
        # Phase 1: interpret freeform input against the current world and session context.
        interpretation = self._interpret_input(raw_input)
        self._last_interpreted_input = interpretation
        if interpretation.no_active_conversation:
            self._last_action_resolution = None
            return CommandResult(output_text="There is no active conversation to continue.")

        # Phase 2: normalize to the canonical structured command.
        normalized_action = self._normalize_action(raw_input, interpretation)
        self._last_normalized_action = normalized_action
        if not normalized_action.is_success:
            self._last_action_resolution = None
            return CommandResult(output_text=normalized_action.failure_reason or "I could not normalize that input into a supported action.")
        command = normalized_action.command
        assert command is not None

        # Phase 3: handle session-level commands that do not enter the world pipeline.
        session_result = self._handle_session_command(command)
        if session_result is not None:
            self._last_action_resolution = None
            return session_result

        # Phase 4: adjudicate the command against the current world state.
        adjudication = self._adjudicate_command(command)
        if adjudication.is_blocked:
            turn = self._build_blocked_resolution_turn(normalized_action, adjudication)
            self._last_action_resolution = turn
            return turn.to_command_result()

        # Phase 5: execute the canonical command.
        result = self._execute_command(command)
        if result.should_quit:
            turn = self._build_final_resolution_turn(
                normalized_action=normalized_action,
                adjudication=adjudication,
                check=None,
                consequence_summary=ActionConsequenceSummary(),
                result=result,
            )
            self._last_action_resolution = turn
            return result

        # Phase 6: update session-local dialogue state and fold in any talk-side plot progress.
        result = self._apply_talk_after_effects(command, result)

        # Phase 7: apply deterministic world consequences.
        result, check_outcome, consequence_summary = self._apply_consequences_phase(command, result, adjudication)

        # Phase 8: advance NPC schedules after world time has settled.
        result = self._apply_npc_updates_phase(command, result)

        # Phase 9: advance authored plot state using the final post-action world state.
        result = self._apply_plot_progression_phase(command, result)

        # Phase 10: render the final response for the player.
        final_result = self._render_response(command, result)
        turn = self._build_final_resolution_turn(
            normalized_action=normalized_action,
            adjudication=adjudication,
            check=check_outcome,
            consequence_summary=consequence_summary,
            result=final_result,
        )
        self._last_action_resolution = turn
        return final_result

    def get_world_state(self) -> WorldState:
        return self._world_state

    def get_last_interpreted_input(self) -> InterpretedInput | None:
        return self._last_interpreted_input

    def get_last_normalized_action(self) -> NormalizedActionInput | None:
        return self._last_normalized_action

    def get_last_action_resolution(self) -> ActionResolutionTurn | None:
        return self._last_action_resolution

    def get_conversation_focus_npc_id(self) -> str | None:
        return self._conversation_context.focus_npc_id

    def get_conversation_stance(self) -> ConversationStance:
        return self._conversation_context.stance

    def _interpret_input(self, raw_input: str) -> InterpretedInput:
        self._conversation_context.sync_with_world(self._world_state)
        return self._input_interpreter.interpret(raw_input, self._world_state, self._conversation_context.focus_npc_id)

    def _normalize_action(self, raw_input: str, interpretation: InterpretedInput) -> NormalizedActionInput:
        if interpretation.fallback_to_parser:
            if not self._looks_like_canonical_command(raw_input):
                return NormalizedActionInput(
                    raw_input=raw_input,
                    command_text=None,
                    command=None,
                    source=NormalizationSource.FAILED,
                    failure_reason=f"Unsupported freeform input: {interpretation.match_reason}.",
                )

            command_text = self._normalize_whitespace(raw_input)
            try:
                command = parse_command(command_text)
            except CommandParseError as exc:
                return NormalizedActionInput(
                    raw_input=raw_input,
                    command_text=command_text,
                    command=None,
                    source=NormalizationSource.FAILED,
                    failure_reason=f"Invalid canonical command: {exc}",
                )

            if isinstance(command, TalkCommand):
                return self._finalize_talk_normalization(raw_input, command_text, command, None, NormalizationSource.DIRECT_COMMAND)
            return NormalizedActionInput(
                raw_input=raw_input,
                command_text=command_text,
                command=command,
                source=NormalizationSource.DIRECT_COMMAND,
            )

        command_text = interpretation.canonical_command
        assert command_text is not None
        try:
            command = parse_command(command_text)
        except CommandParseError as exc:
            return NormalizedActionInput(
                raw_input=raw_input,
                command_text=command_text,
                command=None,
                source=NormalizationSource.FAILED,
                interpretation=interpretation,
                failure_reason=f"Normalized interpretation could not be parsed: {exc}",
            )

        if isinstance(command, TalkCommand):
            return self._finalize_talk_normalization(raw_input, command_text, command, interpretation, NormalizationSource.INTERPRETED)

        return NormalizedActionInput(
            raw_input=raw_input,
            command_text=command_text,
            command=command,
            source=NormalizationSource.INTERPRETED,
            interpretation=interpretation,
        )

    def _normalize_whitespace(self, raw_input: str) -> str:
        return " ".join(raw_input.strip().split())

    def _looks_like_canonical_command(self, raw_input: str) -> bool:
        normalized_input = self._normalize_whitespace(raw_input)
        if not normalized_input:
            return False
        keyword = normalized_input.split(" ", 1)[0].lower()
        return keyword in {"look", "status", "help", "investigate", "save", "load", "quit", "move", "wait", "talk"}

    def _finalize_talk_normalization(
        self,
        raw_input: str,
        command_text: str,
        command: Command,
        interpretation: InterpretedInput | None,
        source: NormalizationSource,
    ) -> NormalizedActionInput:
        assert isinstance(command, TalkCommand)
        if self._conversation_context.focus_npc_id not in (None, command.npc_id):
            self._conversation_context.clear()
        if interpretation is not None and interpretation.dialogue_metadata is not None:
            command = replace(
                command,
                dialogue_metadata=interpretation.dialogue_metadata,
                conversation_stance=self._conversation_context.stance,
            )
        else:
            command = replace(command, conversation_stance=self._conversation_context.stance)

        return NormalizedActionInput(
            raw_input=raw_input,
            command_text=command_text,
            command=command,
            source=source,
            interpretation=interpretation,
        )

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

    def _build_blocked_resolution_turn(
        self,
        normalized_action: NormalizedActionInput,
        adjudication: ActionAdjudicationOutcome,
    ) -> ActionResolutionTurn:
        assert adjudication.blocked_feedback is not None
        return ActionResolutionTurn(
            normalized_action=normalized_action,
            adjudication=adjudication,
            check=None,
            consequence_summary=ActionConsequenceSummary(),
            output_text=adjudication.blocked_feedback,
            should_quit=False,
            render_scene=False,
            conversation_focus_npc_id=None,
            conversation_stance=None,
        )

    def _build_final_resolution_turn(
        self,
        normalized_action: NormalizedActionInput,
        adjudication: ActionAdjudicationOutcome,
        check: ActionCheckOutcome | None,
        consequence_summary: ActionConsequenceSummary,
        result: CommandResult,
    ) -> ActionResolutionTurn:
        return ActionResolutionTurn(
            normalized_action=normalized_action,
            adjudication=adjudication,
            check=check,
            consequence_summary=consequence_summary,
            output_text=result.output_text,
            should_quit=result.should_quit,
            render_scene=result.render_scene,
            conversation_focus_npc_id=result.conversation_focus_npc_id,
            conversation_stance=result.conversation_stance,
        )

    def _adjudicate_command(self, command: Command) -> ActionAdjudicationOutcome:
        adjudication = adjudicate_command(self._world_state, command)
        return adjudication_outcome_from_decision(adjudication)

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
        adjudication: ActionAdjudicationOutcome,
    ) -> tuple[CommandResult, ActionCheckOutcome | None, ActionConsequenceSummary]:
        if not result.render_scene or not adjudication.requires_roll:
            return result, None, ActionConsequenceSummary()

        check_outcome = self._resolve_check(command, adjudication)
        consequence_messages = apply_consequences(self._world_state, command, roll_result=check_outcome)
        return result, check_outcome, ActionConsequenceSummary(messages=tuple(consequence_messages))

    def _resolve_check(self, command: Command, adjudication: ActionAdjudicationOutcome) -> ActionCheckOutcome:
        assert adjudication.check_spec is not None
        check_resolution = resolve_deterministic_check(adjudication.check_spec)
        self._world_state.append_event(
            EventLogEntry(
                timestamp=self._world_state.current_time,
                description=(
                    f"Rolled {check_resolution.kind.value} check: {check_resolution.roll_pool} dice vs difficulty {check_resolution.difficulty}: "
                    f"{check_resolution.individual_rolls} -> {check_resolution.successes} successes."
                ),
                involved_entities=[
                    self._world_state.player.id,
                    self._world_state.player.location_id or "",
                    check_resolution.kind.value,
                ],
            )
        )
        return ActionCheckOutcome.from_resolution(check_resolution)

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
