from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from .action_resolution import (
    ActionAdjudicationOutcome,
    ActionCheckOutcome,
    ActionConsequenceSummary,
    ActionResolutionTurn,
    ActionBlockReason,
    NormalizationSource,
    NormalizedActionInput,
    TurnOutcomeKind,
    adjudication_outcome_from_decision,
)
from .adjudication_engine import adjudicate_command
from .adventure_loader import load_adv1_plot_investigation_rules, load_adv1_plot_progression_rules
from .command_dispatcher import execute_command
from .command_models import Command, ConversationStance, DialogueAct, DialogueMetadata, InvestigateCommand, LoadCommand, MoveCommand, SaveCommand, TalkCommand, WaitCommand
from .exceptions import CommandParseError
from .command_parser import parse_command
from .command_result import CommandResult, DialoguePresentation
from .consequence_engine import apply_post_resolution_consequences
from .conversation_context import ConversationContext, DialogueHistoryEntry
from .data_paths import ensure_adventure_directories, get_default_save_path
from .dialogue_adjudication import DialogueAdjudicationOutcome, DialogueTopicStatus, adjudicate_dialogue_talk
from .dialogue_domain import DialogueDomain
from .dialogue_renderer import DialogueRenderInput, DialogueRenderer, build_dialogue_render_input
from .dialogue_intent_adapter import DialogueIntentAdapter
from .dialogue_subtopic import DialogueSubtopic, detect_dialogue_subtopic
from .dice_engine import DeterministicCheckKind, DeterministicCheckSpecification, resolve_deterministic_check
from .command_registry import CommandModeKind, CommandRegistry, CommandRegistryResult
from .input_interpreter import InputInterpreter, InterpretedInput
from .models import EventLogEntry
from .narrative_provider import SceneNarrativeProvider
from .config import load_config
from .openai_dialogue_renderer import OpenAIDialogueRenderer
from .openai_narrative_provider import OpenAISceneNarrativeProvider
from .dialogue_intent_adapter import OpenAIDialogueIntentAdapter
from .npc_engine import update_npcs_for_current_time
from .plot_engine import advance_plots
from .sample_world import build_sample_world
from .serialization import load_world_state, save_world_state
from .social_models import LogisticsCommitment, SocialCheckResult, SocialOutcomeKind, SocialOutcomePacket, SocialStanceShift, TopicResult
from .social_resolution import evaluate_topic_openness
from .world_state import WorldState


class GameSession:
    def __init__(
        self,
        world_state: WorldState | None = None,
        scene_provider: SceneNarrativeProvider | None = None,
        dialogue_intent_adapter: DialogueIntentAdapter | None = None,
        dialogue_renderer: DialogueRenderer | None = None,
        save_path: str | Path | None = None,
        command_prefix: str | None = None,
    ) -> None:
        self._world_state = world_state if world_state is not None else build_sample_world()
        config = load_config()
        self._command_prefix = command_prefix if command_prefix is not None else config.command_prefix
        self._command_registry = CommandRegistry(self._command_prefix)
        self._scene_provider = (
            scene_provider
            if scene_provider is not None
            else OpenAISceneNarrativeProvider(api_key=config.openai_api_key or "", model=config.openai_model)
        )
        self._input_interpreter = InputInterpreter()
        self._dialogue_intent_adapter = (
            dialogue_intent_adapter
            if dialogue_intent_adapter is not None
            else OpenAIDialogueIntentAdapter(api_key=config.openai_api_key or "", model=config.openai_model)
        )
        self._dialogue_renderer = (
            dialogue_renderer
            if dialogue_renderer is not None
            else OpenAIDialogueRenderer(api_key=config.openai_api_key or "", model=config.openai_model)
        )
        self._last_interpreted_input: InterpretedInput | None = None
        self._last_normalized_action: NormalizedActionInput | None = None
        self._last_action_resolution: ActionResolutionTurn | None = None
        self._conversation_context = ConversationContext()
        self._save_path = Path(save_path) if save_path is not None else get_default_save_path()

    def get_startup_text(self) -> str:
        return self._render_scene_text()

    def process_input(self, raw_input: str) -> CommandResult:
        self._conversation_context.sync_with_world(self._world_state)
        previous_focus_npc_id = self._conversation_context.focus_npc_id
        prefixed_command_text = self._strip_command_prefix(raw_input)
        if prefixed_command_text is not None:
            return self._process_prefixed_input(raw_input, prefixed_command_text, previous_focus_npc_id)

        if previous_focus_npc_id is not None:
            return self._process_forced_dialogue_input(raw_input, previous_focus_npc_id)

        return self._process_reflection_input(raw_input)

    def _strip_command_prefix(self, raw_input: str) -> str | None:
        normalized_input = raw_input.lstrip()
        if not normalized_input.startswith(self._command_prefix):
            return None
        return normalized_input[len(self._command_prefix) :].strip()

    def _process_prefixed_input(
        self,
        raw_input: str,
        command_text: str,
        previous_focus_npc_id: str | None,
    ) -> CommandResult:
        normalized_command = self._normalize_whitespace(command_text)
        if not normalized_command:
            self._last_interpreted_input = None
            self._last_normalized_action = None
            self._last_action_resolution = None
            return CommandResult(output_text="Input after the command prefix cannot be empty.")

        registry_result = self._command_registry.classify(command_text, self._world_state, self._input_interpreter)
        if registry_result.kind is CommandModeKind.HELP:
            return self._process_help_command(raw_input, normalized_command, registry_result.output_text or self._command_registry.build_help_text())
        if registry_result.kind is CommandModeKind.UNSUPPORTED:
            return self._process_unknown_prefixed_command(raw_input, normalized_command, registry_result.output_text or "That command is recognized, but this action is not implemented yet.")
        if registry_result.kind is CommandModeKind.UNKNOWN:
            return self._process_unknown_prefixed_command(raw_input, normalized_command, registry_result.output_text or self._command_registry.build_unknown_command_help_text())
        if registry_result.kind is CommandModeKind.STOP_CONVERSATION:
            return self._process_stop_talking_command(raw_input, normalized_command)
        if registry_result.kind is CommandModeKind.START_CONVERSATION:
            return self._process_start_conversation_command(raw_input, normalized_command, registry_result, previous_focus_npc_id)
        if registry_result.kind is not CommandModeKind.EXECUTE:
            return self._process_unknown_prefixed_command(raw_input, normalized_command, self._command_registry.build_unknown_command_help_text())

        assert registry_result.command is not None
        assert registry_result.interpreted_input is not None
        self._last_interpreted_input = registry_result.interpreted_input
        normalized_action = NormalizedActionInput(
            raw_input=raw_input,
            command_text=registry_result.command_text,
            command=registry_result.command,
            source=NormalizationSource.DIRECT_COMMAND,
            interpretation=registry_result.interpreted_input,
        )
        self._last_normalized_action = normalized_action
        return self._resolve_command_turn(normalized_action, previous_focus_npc_id)

    def _process_forced_dialogue_input(self, raw_input: str, previous_focus_npc_id: str | None) -> CommandResult:
        interpretation = self._interpret_input(raw_input)
        self._last_interpreted_input = interpretation

        if interpretation.failure_reason is None and interpretation.normalized_intent == "talk" and interpretation.canonical_command is not None:
            normalized_action = self._normalize_action(raw_input, interpretation)
            self._last_normalized_action = normalized_action
            if normalized_action.is_success and isinstance(normalized_action.command, TalkCommand):
                return self._resolve_command_turn(normalized_action, previous_focus_npc_id)

        return self._force_dialogue_from_current_focus(raw_input, previous_focus_npc_id)

    def _force_dialogue_from_current_focus(self, raw_input: str, previous_focus_npc_id: str | None) -> CommandResult:
        focus_npc_id = self._conversation_context.focus_npc_id
        if focus_npc_id is None:
            return self._process_reflection_input(raw_input)

        focus_npc = self._world_state.npcs.get(focus_npc_id)
        if focus_npc is None:
            return self._process_reflection_input(raw_input)

        normalized_text = self._input_interpreter._normalize_text(raw_input)
        speech_text = raw_input.strip()
        dialogue_act = self._input_interpreter._classify_dialogue_act(raw_input, normalized_text, speech_text, normalized_text)
        dialogue_move = self._input_interpreter._classify_dialogue_move(raw_input, normalized_text, speech_text, normalized_text, dialogue_act)
        topic = self._input_interpreter._infer_dialogue_topic(normalized_text, dialogue_act, self._conversation_context.subtopic)
        tone = self._input_interpreter._infer_dialogue_tone(normalized_text, dialogue_act, dialogue_move)
        metadata = DialogueMetadata(
            utterance_text=speech_text,
            speech_text=speech_text,
            dialogue_act=dialogue_act,
            topic=topic,
            tone=tone,
            dialogue_move=dialogue_move,
        )
        command = TalkCommand(
            npc_id=focus_npc_id,
            dialogue_metadata=metadata,
            conversation_stance=self._conversation_context.stance,
            conversation_subtopic=self._conversation_context.subtopic,
        )
        interpretation = InterpretedInput(
            normalized_intent="talk",
            target_text=focus_npc.name,
            target_reference=focus_npc_id,
            canonical_command=f"talk {focus_npc_id}",
            confidence=1.0,
            match_reason="unprefixed input was forced into the active conversation path",
            fallback_to_parser=False,
            dialogue_metadata=metadata,
        )
        normalized_action = NormalizedActionInput(
            raw_input=raw_input,
            command_text=f"talk {focus_npc_id}",
            command=command,
            source=NormalizationSource.INTERPRETED,
            interpretation=interpretation,
        )
        self._last_interpreted_input = interpretation
        self._last_normalized_action = normalized_action
        return self._resolve_command_turn(normalized_action, previous_focus_npc_id)

    def _process_help_command(self, raw_input: str, command_text: str, output_text: str) -> CommandResult:
        normalized_action = NormalizedActionInput(
            raw_input=raw_input,
            command_text=command_text,
            command=None,
            source=NormalizationSource.DIRECT_COMMAND,
        )
        turn = ActionResolutionTurn(
            normalized_action=normalized_action,
            adjudication=ActionAdjudicationOutcome.automatic("help requested"),
            check=None,
            consequence_summary=ActionConsequenceSummary(),
            turn_kind=TurnOutcomeKind.SESSION_COMMAND,
            canonical_action_text=command_text,
            normalization_source=normalized_action.source,
            block_reason=None,
            check_kind=None,
            applied_effects=(),
            world_state_mutated=False,
            output_text=output_text,
            should_quit=False,
            render_scene=False,
            conversation_focus_npc_id=self._conversation_context.focus_npc_id,
            conversation_stance=self._conversation_context.stance,
        )
        self._last_interpreted_input = None
        self._last_normalized_action = normalized_action
        self._last_action_resolution = turn
        return turn.to_command_result()

    def _process_start_conversation_command(
        self,
        raw_input: str,
        command_text: str,
        registry_result: CommandRegistryResult,
        previous_focus_npc_id: str | None,
    ) -> CommandResult:
        npc_id = registry_result.target_npc_id
        npc_name = registry_result.target_npc_name
        if npc_id is None or npc_name is None:
            return self._process_unknown_prefixed_command(raw_input, command_text, self._command_registry.build_help_text())

        output_text = registry_result.output_text or f"You approach {npc_name}."
        assert registry_result.interpreted_input is not None
        normalized_action = NormalizedActionInput(
            raw_input=raw_input,
            command_text=f"talk {npc_id}",
            command=None,
            source=NormalizationSource.DIRECT_COMMAND,
            interpretation=registry_result.interpreted_input,
        )

        if output_text.startswith("Talk is blocked:"):
            self._write_back_conversation_memory_if_needed()
            turn = ActionResolutionTurn(
                normalized_action=normalized_action,
                adjudication=ActionAdjudicationOutcome.blocked(
                    reason="talk_target_absent",
                    blocked_feedback=output_text,
                    block_reason=ActionBlockReason.TARGET_NOT_PRESENT,
                ),
                check=None,
                consequence_summary=ActionConsequenceSummary(),
                turn_kind=TurnOutcomeKind.BLOCKED,
                canonical_action_text=None,
                normalization_source=normalized_action.source,
                block_reason=ActionBlockReason.TARGET_NOT_PRESENT,
                check_kind=None,
                applied_effects=(),
                world_state_mutated=False,
                output_text=output_text,
                should_quit=False,
                render_scene=False,
                conversation_focus_npc_id=None,
                conversation_stance=ConversationStance.NEUTRAL,
            )
            self._conversation_context.clear(output_text)
            self._last_interpreted_input = registry_result.interpreted_input
            self._last_normalized_action = normalized_action
            self._last_action_resolution = turn
            return turn.to_command_result()

        self._write_back_conversation_memory_if_needed()
        self._conversation_context.set_focus(npc_id)
        turn = ActionResolutionTurn(
            normalized_action=normalized_action,
            adjudication=ActionAdjudicationOutcome.automatic("conversation started by command"),
            check=None,
            consequence_summary=ActionConsequenceSummary(),
            turn_kind=TurnOutcomeKind.SESSION_COMMAND,
            canonical_action_text=f"talk {npc_id}",
            normalization_source=normalized_action.source,
            block_reason=None,
            check_kind=None,
            applied_effects=(),
            world_state_mutated=False,
            output_text=output_text,
            should_quit=False,
            render_scene=False,
            conversation_focus_npc_id=npc_id,
            conversation_stance=ConversationStance.NEUTRAL,
        )
        self._last_interpreted_input = registry_result.interpreted_input
        self._last_normalized_action = normalized_action
        self._last_action_resolution = turn
        return turn.to_command_result()

    def _process_stop_talking_command(self, raw_input: str, command_text: str) -> CommandResult:
        self._write_back_conversation_memory_if_needed()
        self._conversation_context.reset()
        output_text = "Conversation ended."
        normalized_action = NormalizedActionInput(
            raw_input=raw_input,
            command_text=command_text,
            command=None,
            source=NormalizationSource.DIRECT_COMMAND,
            failure_reason=None,
        )
        turn = ActionResolutionTurn(
            normalized_action=normalized_action,
            adjudication=ActionAdjudicationOutcome.automatic("conversation stopped at the player's request"),
            check=None,
            consequence_summary=ActionConsequenceSummary(),
            turn_kind=TurnOutcomeKind.SESSION_COMMAND,
            canonical_action_text=command_text,
            normalization_source=normalized_action.source,
            block_reason=None,
            check_kind=None,
            applied_effects=(),
            world_state_mutated=False,
            output_text=output_text,
            should_quit=False,
            render_scene=False,
            conversation_focus_npc_id=None,
            conversation_stance=ConversationStance.NEUTRAL,
        )
        self._last_interpreted_input = None
        self._last_normalized_action = normalized_action
        self._last_action_resolution = turn
        return turn.to_command_result()

    def _looks_like_prefixed_talk_command(self, command_text: str) -> bool:
        normalized = self._normalize_whitespace(command_text).lower()
        return normalized == "talk" or normalized.startswith("talk ")

    def _is_supported_prefixed_command(self, command_text: str) -> bool:
        normalized = self._normalize_whitespace(command_text).lower()
        if not normalized:
            return False
        keyword = normalized.split(" ", 1)[0]
        return keyword in {"go", "move", "look", "search", "investigate", "wait", "save", "load", "help", "status", "quit"}

    def _process_start_talking_command(
        self,
        raw_input: str,
        command_text: str,
        previous_focus_npc_id: str | None,
    ) -> CommandResult | None:
        target_text = self._normalize_whitespace(command_text)[len("talk") :].strip()
        if target_text.lower().startswith("with "):
            target_text = target_text[5:].strip()
        elif target_text.lower().startswith("to "):
            target_text = target_text[3:].strip()

        if not target_text:
            return None

        npc, is_present, target_state = self._resolve_prefixed_talk_target(target_text)
        if npc is None:
            if target_state == "ambiguous":
                return self._process_unknown_prefixed_command(raw_input, command_text)
            return None

        if not is_present:
            self._write_back_conversation_memory_if_needed()
            location = self._world_state.locations.get(self._world_state.player.location_id or "")
            location_name = location.name if location is not None else (self._world_state.player.location_id or "unknown location")
            feedback = f"Talk is blocked: {npc.name} is not present at {location_name}."
            normalized_action = NormalizedActionInput(
                raw_input=raw_input,
                command_text=command_text,
                command=None,
                source=NormalizationSource.FAILED,
                failure_reason=feedback,
            )
            turn = ActionResolutionTurn(
                normalized_action=normalized_action,
                adjudication=ActionAdjudicationOutcome.blocked(
                    reason="talk_target_absent",
                    blocked_feedback=feedback,
                    block_reason=ActionBlockReason.TARGET_NOT_PRESENT,
                ),
                check=None,
                consequence_summary=ActionConsequenceSummary(),
                turn_kind=TurnOutcomeKind.BLOCKED,
                canonical_action_text=None,
                normalization_source=normalized_action.source,
                block_reason=ActionBlockReason.TARGET_NOT_PRESENT,
                check_kind=None,
                applied_effects=(),
                world_state_mutated=False,
                output_text=feedback,
                should_quit=False,
                render_scene=False,
                conversation_focus_npc_id=None,
                conversation_stance=ConversationStance.NEUTRAL,
            )
            self._conversation_context.clear(feedback)
            self._last_interpreted_input = None
            self._last_normalized_action = normalized_action
            self._last_action_resolution = turn
            return turn.to_command_result()

        self._write_back_conversation_memory_if_needed()
        self._conversation_context.set_focus(npc.id)
        normalized_action = NormalizedActionInput(
            raw_input=raw_input,
            command_text=command_text,
            command=None,
            source=NormalizationSource.DIRECT_COMMAND,
        )
        self._last_normalized_action = normalized_action
        self._last_interpreted_input = InterpretedInput(
            normalized_intent="start_conversation",
            target_text=npc.name,
            target_reference=npc.id,
            canonical_command=f"talk {npc.id}",
            confidence=1.0,
            match_reason=f"prefixed talk target matched NPC '{npc.name}'",
            fallback_to_parser=False,
            dialogue_metadata=None,
        )
        turn = ActionResolutionTurn(
            normalized_action=normalized_action,
            adjudication=ActionAdjudicationOutcome.automatic("conversation started by command"),
            check=None,
            consequence_summary=ActionConsequenceSummary(),
            turn_kind=TurnOutcomeKind.SESSION_COMMAND,
            canonical_action_text=f"talk {npc.id}",
            normalization_source=normalized_action.source,
            block_reason=None,
            check_kind=None,
            applied_effects=(),
            world_state_mutated=False,
            output_text=f"You approach {npc.name}.",
            should_quit=False,
            render_scene=False,
            conversation_focus_npc_id=npc.id,
            conversation_stance=ConversationStance.NEUTRAL,
        )
        self._last_action_resolution = turn
        return turn.to_command_result()

    def _resolve_prefixed_talk_target(self, target_text: str) -> tuple[object | None, bool, str | None]:
        normalized_target = self._input_interpreter._normalize_text(target_text)
        if not normalized_target:
            return None, False, None

        matches = []
        for npc in self._world_state.npcs.values():
            aliases = [npc.id, self._input_interpreter._normalize_text(npc.name)]
            aliases.extend(self._input_interpreter._npc_aliases(npc.name))
            alias_match = self._input_interpreter._match_alias(normalized_target, aliases)
            if alias_match is None:
                continue
            matches.append(npc)

        if len(matches) > 1:
            return None, False, "ambiguous"
        if len(matches) == 1:
            npc = matches[0]
            return npc, npc.location_id == self._world_state.player.location_id, None

        return None, False, None

    def _process_unknown_prefixed_command(self, raw_input: str, command_text: str, output_text: str | None = None) -> CommandResult:
        if output_text is None:
            output_text = self._command_registry.build_unknown_command_help_text()
        normalized_action = NormalizedActionInput(
            raw_input=raw_input,
            command_text=command_text,
            command=None,
            source=NormalizationSource.FAILED,
            failure_reason=output_text,
        )
        turn = ActionResolutionTurn(
            normalized_action=normalized_action,
            adjudication=ActionAdjudicationOutcome.automatic("unknown prefixed command"),
            check=None,
            consequence_summary=ActionConsequenceSummary(),
            turn_kind=TurnOutcomeKind.SESSION_COMMAND,
            canonical_action_text=None,
            normalization_source=normalized_action.source,
            block_reason=None,
            check_kind=None,
            applied_effects=(),
            world_state_mutated=False,
            output_text=output_text,
            should_quit=False,
            render_scene=False,
            conversation_focus_npc_id=self._conversation_context.focus_npc_id,
            conversation_stance=self._conversation_context.stance,
        )
        self._last_interpreted_input = None
        self._last_normalized_action = normalized_action
        self._last_action_resolution = turn
        return turn.to_command_result()

    def _resolve_shortform_talk_candidates(self, target_text: str) -> list:
        normalized_target = self._input_interpreter._normalize_text(target_text)
        if not normalized_target:
            return []

        matches = []
        for npc in self._world_state.npcs.values():
            if npc.location_id != self._world_state.player.location_id:
                continue
            normalized_name = self._input_interpreter._normalize_text(npc.name)
            name_parts = normalized_name.split()
            if normalized_target == normalized_name or normalized_target == npc.id:
                matches.append(npc)
                continue
            if normalized_target in name_parts:
                matches.append(npc)
        return matches

    def _process_reflection_input(self, raw_input: str) -> CommandResult:
        reflection_text = self._build_reflection_text(raw_input)
        normalized_action = NormalizedActionInput(
            raw_input=raw_input,
            command_text=None,
            command=None,
            source=NormalizationSource.REFLECTION,
        )
        turn = self._build_reflection_resolution_turn(normalized_action, reflection_text)
        self._last_interpreted_input = None
        self._last_normalized_action = normalized_action
        self._last_action_resolution = turn
        return turn.to_command_result()

    def _build_reflection_resolution_turn(
        self,
        normalized_action: NormalizedActionInput,
        reflection_text: str,
    ) -> ActionResolutionTurn:
        return ActionResolutionTurn(
            normalized_action=normalized_action,
            adjudication=ActionAdjudicationOutcome.automatic("unprefixed reflection"),
            check=None,
            consequence_summary=ActionConsequenceSummary(),
            turn_kind=TurnOutcomeKind.NON_STATEFUL_ACTION,
            canonical_action_text=None,
            normalization_source=normalized_action.source,
            block_reason=None,
            check_kind=None,
            applied_effects=(),
            world_state_mutated=False,
            output_text=reflection_text,
            should_quit=False,
            render_scene=False,
            conversation_focus_npc_id=None,
            conversation_stance=ConversationStance.NEUTRAL,
        )

    def _build_reflection_text(self, raw_input: str) -> str:
        player_name = self._world_state.player.name or "The player"
        thought = self._normalize_whitespace(raw_input)
        if not thought:
            return f"{player_name} keeps the thought to themselves."
        return f"{player_name} turns the thought over quietly: {thought}"

    def _is_stop_talking_command(self, command_text: str) -> bool:
        normalized = self._normalize_whitespace(command_text).lower()
        if normalized.startswith("stop talking"):
            suffix = normalized.removeprefix("stop talking").strip()
        elif normalized.startswith("quit talking"):
            suffix = normalized.removeprefix("quit talking").strip()
        else:
            return False
        if not suffix:
            return True
        return suffix.startswith("with ") or suffix.startswith("to ")

    def _resolve_command_turn(self, normalized_action: NormalizedActionInput, previous_focus_npc_id: str | None) -> CommandResult:
        command = normalized_action.command
        assert command is not None

        dialogue_adjudication = None
        if isinstance(command, TalkCommand):
            dialogue_adjudication = self._adjudicate_dialogue(command)
            if dialogue_adjudication.is_blocked:
                turn = self._build_blocked_resolution_turn(normalized_action, self._blocked_action_adjudication_from_dialogue(dialogue_adjudication), dialogue_adjudication)
                self._last_action_resolution = turn
                return turn.to_command_result()
            if dialogue_adjudication.is_escalated and command.dialogue_metadata is not None and command.dialogue_metadata.dialogue_act is DialogueAct.PERSUADE:
                result, adjudication, check_outcome, consequence_summary = self._resolve_escalated_persuade_dialogue(command, dialogue_adjudication)
                turn = self._build_final_resolution_turn(
                    command=command,
                    normalized_action=normalized_action,
                    adjudication=adjudication,
                    check=check_outcome,
                    consequence_summary=consequence_summary,
                    result=self._render_talk_result(command, result, dialogue_adjudication, check_outcome, consequence_summary, previous_focus_npc_id),
                    dialogue_adjudication=dialogue_adjudication,
                    social_outcome=self._finalize_social_outcome_packet(
                        command,
                        dialogue_adjudication,
                        result.conversation_stance or dialogue_adjudication.conversation_stance,
                        check_outcome,
                        consequence_summary,
                    ),
                )
                self._last_action_resolution = turn
                return turn.to_command_result()
            if not dialogue_adjudication.is_allowed:
                result = self._materialize_dialogue_adjudication_result(command, dialogue_adjudication)
                result = self._render_talk_result(command, result, dialogue_adjudication, None, ActionConsequenceSummary(), previous_focus_npc_id)
                turn = self._build_dialogue_adjudication_resolution_turn(command, normalized_action, dialogue_adjudication, result)
                self._last_action_resolution = turn
                return result

        session_result = self._handle_session_command(command)
        if session_result is not None:
            self._last_action_resolution = None
            return session_result

        adjudication = self._adjudicate_command(command)
        if adjudication.is_blocked:
            turn = self._build_blocked_resolution_turn(normalized_action, adjudication)
            self._last_action_resolution = turn
            return turn.to_command_result()

        if isinstance(command, TalkCommand) and dialogue_adjudication is not None:
            result = self._execute_talk_command(command, dialogue_adjudication.dialogue_domain, dialogue_adjudication.social_outcome)
        else:
            result = self._execute_command(command)
            if isinstance(command, MoveCommand):
                focused_npc = self._world_state.npcs.get(self._conversation_context.focus_npc_id or "")
                location = self._world_state.locations.get(self._world_state.player.location_id or "")
                self._write_back_conversation_memory_if_needed()
                if focused_npc is not None and location is not None:
                    self._conversation_context.clear(
                        f"Talk is blocked: {focused_npc.name} is not present at {location.name}, so that conversation cannot continue."
                    )
                else:
                    self._conversation_context.clear("Talk continuity was cleared by movement.")
            elif isinstance(command, (WaitCommand, InvestigateCommand)):
                self._conversation_context.clear_subtopic()
        if result.should_quit:
            turn = self._build_final_resolution_turn(
                command=command,
                normalized_action=normalized_action,
                adjudication=adjudication,
                check=None,
                consequence_summary=ActionConsequenceSummary(),
                result=result,
                dialogue_adjudication=dialogue_adjudication,
                social_outcome=self._finalize_social_outcome_packet(
                    command,
                    dialogue_adjudication,
                    result.conversation_stance or dialogue_adjudication.conversation_stance,
                    None,
                    ActionConsequenceSummary(),
                ) if dialogue_adjudication is not None else None,
            )
            self._last_action_resolution = turn
            return result

        result = self._apply_talk_after_effects(command, result, dialogue_adjudication)
        result, check_outcome, consequence_summary = self._apply_post_resolution_consequences_phase(command, result, adjudication)
        result = self._apply_npc_updates_phase(command, result)
        result = self._apply_plot_progression_phase(command, result)
        final_result = self._render_response(command, result)
        if isinstance(command, InvestigateCommand) and consequence_summary.messages:
            investigation_rules = load_adv1_plot_investigation_rules()
            plot = self._world_state.plots.get(investigation_rules.plot_id)
            if plot is not None and plot.active:
                final_result = self._append_consequence_summary_to_result(final_result, consequence_summary)
        final_result = self._render_talk_result(command, final_result, dialogue_adjudication, check_outcome, consequence_summary, previous_focus_npc_id)
        turn = self._build_final_resolution_turn(
            command=command,
            normalized_action=normalized_action,
            adjudication=adjudication,
            check=check_outcome,
            consequence_summary=consequence_summary,
            result=final_result,
            dialogue_adjudication=dialogue_adjudication,
            social_outcome=self._finalize_social_outcome_packet(
                command,
                dialogue_adjudication,
                final_result.conversation_stance or dialogue_adjudication.conversation_stance,
                check_outcome,
                consequence_summary,
            ) if dialogue_adjudication is not None else None,
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

    def get_conversation_subtopic(self) -> DialogueSubtopic | None:
        return self._conversation_context.subtopic

    def get_recent_dialogue_history(self) -> tuple[DialogueHistoryEntry, ...]:
        return self._conversation_context.recent_dialogue_history

    def _interpret_input(self, raw_input: str) -> InterpretedInput:
        self._conversation_context.sync_with_world(self._world_state)
        return self._input_interpreter.interpret(
            raw_input,
            self._world_state,
            self._conversation_context.focus_npc_id,
            self._conversation_context.subtopic,
            self._conversation_context.stale_focus_npc_id,
            self._conversation_context.stale_focus_reason,
            self._dialogue_intent_adapter,
            self._conversation_context.recent_dialogue_history,
        )

    def _normalize_action(self, raw_input: str, interpretation: InterpretedInput) -> NormalizedActionInput:
        if interpretation.failure_reason is not None:
            if interpretation.normalized_intent == "talk":
                self._conversation_context.reset()
            return NormalizedActionInput(
                raw_input=raw_input,
                command_text=None,
                command=None,
                source=NormalizationSource.FAILED,
                interpretation=interpretation,
                failure_reason=interpretation.failure_reason,
            )

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
            self._write_back_conversation_memory_if_needed()
            self._conversation_context.clear()
        if interpretation is not None and interpretation.dialogue_metadata is not None:
            command = replace(
                command,
                dialogue_metadata=interpretation.dialogue_metadata,
                conversation_stance=self._conversation_context.stance,
                conversation_subtopic=self._conversation_context.subtopic,
            )
        else:
            command = replace(
                command,
                conversation_stance=self._conversation_context.stance,
                conversation_subtopic=self._conversation_context.subtopic,
            )

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
            self._conversation_context.clear("Talk is blocked: the current conversation was reset when the save was loaded.")
            if not self._save_path.exists():
                return CommandResult(output_text=f"No save file found at {self._save_path.as_posix()}.")
            self._world_state = load_world_state(self._save_path)
            return CommandResult(output_text=self._render_scene_text(), render_scene=True)

        return None

    def _build_blocked_resolution_turn(
        self,
        normalized_action: NormalizedActionInput,
        adjudication: ActionAdjudicationOutcome,
        dialogue_adjudication: DialogueAdjudicationOutcome | None = None,
    ) -> ActionResolutionTurn:
        assert adjudication.blocked_feedback is not None
        return ActionResolutionTurn(
            normalized_action=normalized_action,
            adjudication=adjudication,
            check=None,
            consequence_summary=ActionConsequenceSummary(),
            turn_kind=TurnOutcomeKind.BLOCKED,
            canonical_action_text=normalized_action.canonical_command_text,
            normalization_source=normalized_action.source,
            block_reason=adjudication.block_reason,
            check_kind=None,
            applied_effects=(),
            world_state_mutated=False,
            output_text=adjudication.blocked_feedback,
            should_quit=False,
            render_scene=False,
            conversation_focus_npc_id=None,
            conversation_stance=None,
            dialogue_adjudication=dialogue_adjudication,
            social_outcome=dialogue_adjudication.social_outcome if dialogue_adjudication is not None else None,
        )

    def _build_final_resolution_turn(
        self,
        command: Command,
        normalized_action: NormalizedActionInput,
        adjudication: ActionAdjudicationOutcome,
        check: ActionCheckOutcome | None,
        consequence_summary: ActionConsequenceSummary,
        result: CommandResult,
        dialogue_adjudication: DialogueAdjudicationOutcome | None = None,
        social_outcome: SocialOutcomePacket | None = None,
    ) -> ActionResolutionTurn:
        turn_kind = self._classify_turn_kind(command, adjudication, consequence_summary)
        return ActionResolutionTurn(
            normalized_action=normalized_action,
            adjudication=adjudication,
            check=check,
            consequence_summary=consequence_summary,
            turn_kind=turn_kind,
            canonical_action_text=normalized_action.canonical_command_text,
            normalization_source=normalized_action.source,
            block_reason=adjudication.block_reason,
            check_kind=check.kind if check is not None else None,
            applied_effects=consequence_summary.applied_effects,
            world_state_mutated=turn_kind is TurnOutcomeKind.STATEFUL_ACTION,
            output_text=result.output_text,
            should_quit=result.should_quit,
            render_scene=result.render_scene,
            conversation_focus_npc_id=result.conversation_focus_npc_id,
            conversation_stance=result.conversation_stance,
            dialogue_presentation=result.dialogue_presentation,
            dialogue_adjudication=dialogue_adjudication,
            social_outcome=social_outcome,
        )

    def _build_dialogue_adjudication_resolution_turn(
        self,
        command: TalkCommand,
        normalized_action: NormalizedActionInput,
        dialogue_adjudication: DialogueAdjudicationOutcome,
        result: CommandResult,
    ) -> ActionResolutionTurn:
        return ActionResolutionTurn(
            normalized_action=normalized_action,
            adjudication=ActionAdjudicationOutcome.automatic(dialogue_adjudication.reason_code),
            check=None,
            consequence_summary=ActionConsequenceSummary(),
            turn_kind=TurnOutcomeKind.STATEFUL_ACTION,
            canonical_action_text=normalized_action.canonical_command_text,
            normalization_source=normalized_action.source,
            block_reason=None,
            check_kind=None,
            applied_effects=(),
            world_state_mutated=False,
            output_text=result.output_text,
            should_quit=result.should_quit,
            render_scene=result.render_scene,
            conversation_focus_npc_id=result.conversation_focus_npc_id,
            conversation_stance=result.conversation_stance,
            dialogue_presentation=result.dialogue_presentation,
            dialogue_adjudication=dialogue_adjudication,
            social_outcome=self._finalize_social_outcome_packet(
                command,
                dialogue_adjudication,
                result.conversation_stance or dialogue_adjudication.conversation_stance,
                None,
                ActionConsequenceSummary(),
            ),
        )

    def _adjudicate_command(self, command: Command) -> ActionAdjudicationOutcome:
        adjudication = adjudicate_command(self._world_state, command)
        return adjudication_outcome_from_decision(adjudication)

    def _adjudicate_dialogue(self, command: TalkCommand) -> DialogueAdjudicationOutcome:
        return adjudicate_dialogue_talk(self._world_state, command)

    def _blocked_action_adjudication_from_dialogue(
        self,
        dialogue_adjudication: DialogueAdjudicationOutcome,
    ) -> ActionAdjudicationOutcome:
        assert dialogue_adjudication.blocked_feedback is not None
        return ActionAdjudicationOutcome.blocked(
            reason=dialogue_adjudication.reason_code,
            blocked_feedback=dialogue_adjudication.blocked_feedback,
            block_reason=ActionBlockReason.TARGET_NOT_PRESENT,
        )

    def _execute_command(self, command: Command) -> CommandResult:
        return execute_command(self._world_state, command)

    def _execute_talk_command(
        self,
        command: TalkCommand,
        dialogue_domain: DialogueDomain | None,
        social_outcome: SocialOutcomePacket | None,
    ) -> CommandResult:
        next_stance = command.conversation_stance
        if social_outcome is not None:
            next_stance = social_outcome.stance_shift.to_stance
        return CommandResult(
            output_text="",
            conversation_focus_npc_id=command.npc_id,
            conversation_stance=next_stance,
        )

    def _materialize_dialogue_adjudication_result(
        self,
        command: TalkCommand,
        dialogue_adjudication: DialogueAdjudicationOutcome,
    ) -> CommandResult:
        npc = self._world_state.npcs.get(command.npc_id)
        assert npc is not None

        self._conversation_context.set_focus(
            npc.id,
            dialogue_adjudication.conversation_stance,
            self._resolve_next_conversation_subtopic(command, dialogue_adjudication),
        )
        self._sync_npc_social_state(npc.id, dialogue_adjudication.conversation_stance)
        return CommandResult(
            output_text="",
            conversation_focus_npc_id=npc.id,
            conversation_stance=dialogue_adjudication.conversation_stance,
        )

    def _render_talk_result(
        self,
        command: Command,
        result: CommandResult,
        dialogue_adjudication: DialogueAdjudicationOutcome | None,
        check: ActionCheckOutcome | None,
        consequence_summary: ActionConsequenceSummary,
        previous_focus_npc_id: str | None,
    ) -> CommandResult:
        if not isinstance(command, TalkCommand) or dialogue_adjudication is None:
            return result
        if result.output_text.startswith("Talk is blocked:"):
            return result

        try:
            render_social_outcome = self._finalize_social_outcome_packet(
                command,
                dialogue_adjudication,
                result.conversation_stance or dialogue_adjudication.conversation_stance,
                check,
                consequence_summary,
            )
            render_input = build_dialogue_render_input(
                self._world_state,
                command,
                dialogue_adjudication,
                check,
                consequence_summary,
                render_social_outcome,
                self._conversation_context.recent_dialogue_history,
            )
            if not self._supports_dialogue_rendering(render_input):
                return result
            rendered_output = self._dialogue_renderer.render_dialogue(render_input)
            dialogue_presentation = self._build_dialogue_presentation(
                command,
                result,
                previous_focus_npc_id,
            )
            self._record_npc_dialogue_history(command, rendered_output)
        except Exception:
            rendered_output = "Dialogue rendering failed: no realized reply is available right now."
            dialogue_presentation = None

        return CommandResult(
            output_text=rendered_output,
            should_quit=result.should_quit,
            render_scene=result.render_scene,
            conversation_focus_npc_id=result.conversation_focus_npc_id,
            conversation_stance=result.conversation_stance,
            dialogue_presentation=dialogue_presentation,
        )

    def _supports_dialogue_rendering(self, render_input: DialogueRenderInput) -> bool:
        return render_input.social_outcome is not None

    def _build_dialogue_presentation(
        self,
        command: TalkCommand,
        result: CommandResult,
        previous_focus_npc_id: str | None,
    ) -> DialoguePresentation | None:
        if command.dialogue_metadata is None:
            return None
        if result.conversation_focus_npc_id is None:
            return None
        npc = self._world_state.npcs.get(result.conversation_focus_npc_id)
        if npc is None:
            return None
        utterance = command.dialogue_metadata.speech_text or command.dialogue_metadata.utterance_text
        utterance = self._normalize_whitespace(utterance)
        if not utterance:
            return None
        return DialoguePresentation(
            player_utterance=utterance,
            npc_display_name=npc.name,
            focus_changed=result.conversation_focus_npc_id != previous_focus_npc_id,
        )

    def _resolve_escalated_persuade_dialogue(
        self,
        command: TalkCommand,
        dialogue_adjudication: DialogueAdjudicationOutcome,
    ) -> tuple[CommandResult, ActionAdjudicationOutcome, ActionCheckOutcome, ActionConsequenceSummary]:
        check_spec = self._build_dialogue_social_check_spec(command, dialogue_adjudication)
        adjudication = ActionAdjudicationOutcome.check_gated(
            reason=dialogue_adjudication.reason_code,
            check_spec=check_spec,
        )
        check_outcome = self._resolve_check(command, adjudication)

        if check_outcome.is_success:
            consequence_summary = self._apply_dialogue_persuade_success_consequences(command, dialogue_adjudication, check_outcome)
            result = self._execute_talk_command(command, dialogue_adjudication.dialogue_domain, dialogue_adjudication.social_outcome)
            result = self._apply_talk_after_effects(command, result, dialogue_adjudication)
            return result, adjudication, check_outcome, consequence_summary

        consequence_summary = self._apply_dialogue_persuade_failure_consequences(command, dialogue_adjudication, check_outcome)
        result = self._materialize_dialogue_persuade_failure_result(command, dialogue_adjudication, consequence_summary)
        return result, adjudication, check_outcome, consequence_summary

    def _build_dialogue_social_check_spec(
        self,
        command: TalkCommand,
        dialogue_adjudication: DialogueAdjudicationOutcome,
    ) -> DeterministicCheckSpecification:
        npc = self._world_state.npcs.get(command.npc_id)
        assert npc is not None
        plot_rules = load_adv1_plot_progression_rules()
        topic = command.dialogue_metadata.topic if command.dialogue_metadata is not None else None
        normalized_topic = self._normalize_dialogue_topic(topic)
        if not normalized_topic and command.dialogue_metadata is not None:
            normalized_topic = self._normalize_dialogue_topic(
                command.dialogue_metadata.speech_text or command.dialogue_metadata.utterance_text
            )
        evaluation = evaluate_topic_openness(
            npc.social_state,
            normalized_topic or topic,
            DialogueAct.PERSUADE,
            dialogue_adjudication.dialogue_domain,
            dialogue_adjudication.conversation_stance,
        )
        roll_pool = evaluation.check_roll_pool
        difficulty = evaluation.check_difficulty

        return DeterministicCheckSpecification(
            kind=DeterministicCheckKind.DIALOGUE_SOCIAL,
            seed_parts=(
                self._world_state.current_time,
                "talk",
                "persuade",
                command.npc_id,
                normalized_topic or "no-topic",
                self._world_state.player.id,
                str(evaluation.openness_score),
                evaluation.topic_sensitivity.value,
            ),
            roll_pool=roll_pool,
            difficulty=difficulty,
        )

    def _apply_dialogue_persuade_success_consequences(
        self,
        command: TalkCommand,
        dialogue_adjudication: DialogueAdjudicationOutcome,
        check_outcome: ActionCheckOutcome,
    ) -> ActionConsequenceSummary:
        npc = self._world_state.npcs.get(command.npc_id)
        assert npc is not None
        messages: list[str] = []
        applied_effects: list[str] = []

        plot_rules = load_adv1_plot_progression_rules()
        plot = self._world_state.plots.get(plot_rules.plot_id)

        if command.npc_id == plot_rules.talk_npc_id and plot is not None and plot.active and dialogue_adjudication.topic_status is DialogueTopicStatus.PRODUCTIVE:
            previous_stage = plot.stage
            if npc.social_state.trust < plot_rules.talk_minimum_trust_level:
                npc.social_state.trust = plot_rules.talk_minimum_trust_level
                npc.social_state.willingness_to_cooperate = max(npc.social_state.willingness_to_cooperate, 1)
                npc.trust_level = npc.social_state.trust
                applied_effects.append("dialogue_trust_adjusted")
            if plot_rules.talk_required_story_flag not in self._world_state.story_flags:
                self._world_state.add_story_flag(plot_rules.talk_required_story_flag)
                applied_effects.append("dialogue_story_flag_added")
            if previous_stage != plot_rules.talk_to_stage:
                plot.stage = plot_rules.talk_to_stage
                applied_effects.append("dialogue_plot_progressed")
                message = (
                    f"Dialogue check success: {npc.name} shares the dock lead and the Missing Ledger plot advances "
                    f"from {previous_stage} to {plot.stage}."
                )
            else:
                message = f"Dialogue check success: {npc.name} keeps talking and the conversation remains productive."
            messages.append(message)
            self._world_state.append_event(
                EventLogEntry(
                    timestamp=self._world_state.current_time,
                    description=message,
                    involved_entities=[self._world_state.player.id, plot.id, command.npc_id],
                )
            )
        else:
            message = f"Dialogue check success: {npc.name} keeps talking and the conversation remains productive."
            messages.append(message)
            self._world_state.append_event(
                EventLogEntry(
                    timestamp=self._world_state.current_time,
                    description=message,
                    involved_entities=[self._world_state.player.id, command.npc_id],
                )
            )

        applied_effects.append("dialogue_social_check_success")
        return ActionConsequenceSummary(messages=tuple(messages), applied_effects=tuple(applied_effects))

    def _apply_dialogue_persuade_failure_consequences(
        self,
        command: TalkCommand,
        dialogue_adjudication: DialogueAdjudicationOutcome,
        check_outcome: ActionCheckOutcome,
    ) -> ActionConsequenceSummary:
        npc = self._world_state.npcs.get(command.npc_id)
        assert npc is not None
        if dialogue_adjudication.topic_status is DialogueTopicStatus.REFUSED:
            message = f"Dialogue check failed: {npc.name} refuses to move past the guarded topic."
        else:
            message = f"Dialogue check failed: {npc.name} stays guarded and does not advance the Missing Ledger lead."

        self._conversation_context.set_focus(
            npc.id,
            ConversationStance.GUARDED,
            self._resolve_next_conversation_subtopic(command, dialogue_adjudication),
        )
        npc.social_state.current_conversation_stance = ConversationStance.GUARDED
        npc.trust_level = npc.social_state.trust
        self._sync_npc_social_state(npc.id, ConversationStance.GUARDED)
        self._world_state.append_event(
            EventLogEntry(
                timestamp=self._world_state.current_time,
                description=message,
                involved_entities=[self._world_state.player.id, command.npc_id],
            )
        )
        return ActionConsequenceSummary(messages=(message,), applied_effects=("dialogue_social_check_failure",))

    def _materialize_dialogue_persuade_failure_result(
        self,
        command: TalkCommand,
        dialogue_adjudication: DialogueAdjudicationOutcome,
        consequence_summary: ActionConsequenceSummary,
    ) -> CommandResult:
        npc = self._world_state.npcs.get(command.npc_id)
        assert npc is not None
        self._record_player_dialogue_history(command)
        if consequence_summary.messages:
            output_text = "\n".join(consequence_summary.messages)
        elif dialogue_adjudication.topic_status is DialogueTopicStatus.REFUSED:
            output_text = f"Talk is guarded: {npc.name} refuses to go further right now."
        else:
            output_text = f"Talk is guarded: {npc.name} stays guarded and keeps the conversation tight."

        return CommandResult(
            output_text=output_text,
            conversation_focus_npc_id=npc.id,
            conversation_stance=ConversationStance.GUARDED,
        )

    def _append_consequence_summary_to_result(
        self,
        result: CommandResult,
        consequence_summary: ActionConsequenceSummary,
    ) -> CommandResult:
        if not consequence_summary.messages:
            return result

        summary_text = "\n".join(consequence_summary.messages)
        output_text = result.output_text.strip()
        if output_text:
            combined_output = f"{output_text}\n\n{summary_text}"
        else:
            combined_output = summary_text

        return CommandResult(
            output_text=combined_output,
            should_quit=result.should_quit,
            render_scene=result.render_scene,
            conversation_focus_npc_id=result.conversation_focus_npc_id,
            conversation_stance=result.conversation_stance,
            dialogue_presentation=result.dialogue_presentation,
        )

    def _normalize_dialogue_topic(self, topic: str | None) -> str:
        if topic is None:
            return ""
        return " ".join(topic.lower().replace("-", " ").split())

    def _apply_talk_after_effects(
        self,
        command: Command,
        result: CommandResult,
        dialogue_adjudication: DialogueAdjudicationOutcome | None = None,
    ) -> CommandResult:
        if not isinstance(command, TalkCommand):
            return result

        if result.conversation_focus_npc_id is not None:
            self._conversation_context.replace_focus(result.conversation_focus_npc_id)
            self._conversation_context.stance = result.conversation_stance
            self._conversation_context.subtopic = self._resolve_next_conversation_subtopic(
                command,
                dialogue_adjudication,
            )
            if result.conversation_stance is not None:
                self._sync_npc_social_state(result.conversation_focus_npc_id, result.conversation_stance)
        self._record_player_dialogue_history(command)
        return result

    def _record_player_dialogue_history(self, command: TalkCommand) -> None:
        metadata = command.dialogue_metadata
        if metadata is None:
            return
        player_utterance = metadata.speech_text or metadata.utterance_text
        self._conversation_context.record_dialogue_utterance("player", player_utterance)

    def _record_npc_dialogue_history(self, command: TalkCommand, npc_utterance_text: str) -> None:
        if not npc_utterance_text.strip():
            return
        npc = self._world_state.npcs.get(command.npc_id)
        speaker = npc.name if npc is not None else command.npc_id
        self._conversation_context.record_dialogue_utterance(speaker, npc_utterance_text)

    def _write_back_conversation_memory_if_needed(self) -> None:
        focus_npc_id = self._conversation_context.focus_npc_id
        if focus_npc_id is None or not self._conversation_context.recent_dialogue_history:
            return

        npc = self._world_state.npcs.get(focus_npc_id)
        if npc is None:
            return

        player_name = self._world_state.player.name or "The player"
        subtopic = self._conversation_context.subtopic
        topic_label = subtopic.value if subtopic is not None else self._last_dialogue_domain_for_memory(focus_npc_id)
        outcome_label = self._last_dialogue_outcome_for_memory(focus_npc_id)
        player_turns = sum(1 for entry in self._conversation_context.recent_dialogue_history if entry.speaker == "player")
        npc_turns = sum(1 for entry in self._conversation_context.recent_dialogue_history if entry.speaker != "player")

        parts = [
            f"{player_name} last spoke with {npc.name}",
            f"topic={topic_label}",
            f"stance={self._conversation_context.stance.value}",
            f"outcome={outcome_label}",
            f"turns={player_turns}p/{npc_turns}n",
            "memory_only_no_authority",
        ]
        npc.previous_interactions_summary = "; ".join(parts)

    def _last_dialogue_domain_for_memory(self, npc_id: str) -> str:
        turn = self._last_action_resolution
        if turn is None or turn.conversation_focus_npc_id != npc_id or turn.dialogue_adjudication is None:
            return "conversation"
        return turn.dialogue_adjudication.dialogue_domain.value

    def _last_dialogue_outcome_for_memory(self, npc_id: str) -> str:
        turn = self._last_action_resolution
        if turn is None or turn.conversation_focus_npc_id != npc_id:
            return "unknown"
        if turn.social_outcome is not None and turn.social_outcome.logistics_commitment is LogisticsCommitment.ABSOLUTE_REFUSAL:
            return "logistics_refusal"
        if turn.check is not None:
            return "check_success" if turn.check.is_success else "check_failure"
        if turn.social_outcome is not None:
            return turn.social_outcome.outcome_kind.value
        if turn.dialogue_adjudication is not None and turn.dialogue_adjudication.topic_status is DialogueTopicStatus.REFUSED:
            return "refuse"
        return "unknown"

    def _sync_npc_social_state(self, npc_id: str, stance: ConversationStance) -> None:
        npc = self._world_state.npcs.get(npc_id)
        if npc is None:
            return
        if not npc.social_state.relationship_to_player:
            npc.social_state.relationship_to_player = npc.attitude_to_player
        npc.trust_level = npc.social_state.trust
        npc.social_state.current_conversation_stance = stance

    def _finalize_social_outcome_packet(
        self,
        command: TalkCommand,
        dialogue_adjudication: DialogueAdjudicationOutcome,
        final_stance: ConversationStance,
        check: ActionCheckOutcome | None,
        consequence_summary: ActionConsequenceSummary,
    ) -> SocialOutcomePacket:
        base_packet = dialogue_adjudication.social_outcome
        assert base_packet is not None

        check_result = None
        if check is not None:
            check_result = SocialCheckResult(
                kind=check.kind.value,
                seed=check.seed,
                roll_pool=check.roll_pool,
                difficulty=check.difficulty,
                successes=check.successes,
                is_success=check.is_success,
            )

        topic_result = base_packet.topic_result
        outcome_kind = base_packet.outcome_kind
        state_effects, plot_effects = self._split_social_effects(consequence_summary.applied_effects)
        logistics_commitment = self._derive_logistics_commitment(command, dialogue_adjudication, outcome_kind, topic_result)

        if check is not None:
            if check.is_success:
                topic_result = TopicResult.OPENED if dialogue_adjudication.topic_status is DialogueTopicStatus.PRODUCTIVE else TopicResult.PARTIAL
                outcome_kind = SocialOutcomeKind.REVEAL if plot_effects else SocialOutcomeKind.COOPERATE
                logistics_commitment = self._derive_logistics_commitment(command, dialogue_adjudication, outcome_kind, topic_result)
            else:
                topic_result = TopicResult.BLOCKED if dialogue_adjudication.topic_status is DialogueTopicStatus.REFUSED else TopicResult.PARTIAL
                outcome_kind = SocialOutcomeKind.REFUSE
                logistics_commitment = self._derive_logistics_commitment(command, dialogue_adjudication, outcome_kind, topic_result)

        return SocialOutcomePacket(
            outcome_kind=outcome_kind,
            stance_shift=SocialStanceShift(
                from_stance=base_packet.stance_shift.from_stance,
                to_stance=final_stance,
            ),
            check_required=base_packet.check_required,
            check_result=check_result,
            topic_result=topic_result,
            state_effects=state_effects,
            plot_effects=plot_effects,
            reason_code=base_packet.reason_code,
            logistics_commitment=logistics_commitment,
        )

    def _derive_logistics_commitment(
        self,
        command: TalkCommand,
        dialogue_adjudication: DialogueAdjudicationOutcome,
        outcome_kind: SocialOutcomeKind,
        topic_result: TopicResult,
    ) -> LogisticsCommitment:
        subtopic = detect_dialogue_subtopic(command.dialogue_metadata) or command.conversation_subtopic
        logistics_text = self._normalize_dialogue_topic(self._dialogue_metadata_text(command.dialogue_metadata))
        has_logistics_request = subtopic in {
            DialogueSubtopic.BACKUP_OR_STAY_NEARBY,
            DialogueSubtopic.TRANSPORT_OR_VEHICLE_SUPPORT,
            DialogueSubtopic.FARE_OR_MONEY_SUPPORT,
        } or any(
            keyword in logistics_text
            for keyword in (
                "back me up",
                "back up",
                "backup",
                "watch over me",
                "watch out for me",
                "watch my back",
                "cover me",
                "stay nearby",
                "stay close",
                "wait nearby",
                "wait in the car",
                "stay in the car",
                "come along",
                "come with",
                "coming with",
                "join me",
                "drive",
                "ride",
                "lift",
                "car",
                "vehicle",
                "transport",
                "fare",
                "taxi",
                "cab",
                "spare change",
                "pay for the ride",
                "pay for the taxi",
            )
        )
        if not has_logistics_request:
            return LogisticsCommitment.NONE

        if topic_result is TopicResult.BLOCKED or outcome_kind in {SocialOutcomeKind.REFUSE, SocialOutcomeKind.DISENGAGE, SocialOutcomeKind.THREATEN}:
            return LogisticsCommitment.ABSOLUTE_REFUSAL

        if subtopic is None:
            if any(
                keyword in logistics_text
                for keyword in (
                    "backup",
                    "back up",
                    "stay nearby",
                    "stay close",
                    "wait nearby",
                    "stay in the car",
                    "wait in the car",
                    "come along",
                    "come with",
                    "coming with",
                    "join me",
                    "cover me",
                    "watch over me",
                    "watch out for me",
                    "watch my back",
                )
            ):
                subtopic = DialogueSubtopic.BACKUP_OR_STAY_NEARBY
            elif any(keyword in logistics_text for keyword in ("drive", "ride", "lift", "car", "vehicle", "drop me off", "transport")):
                subtopic = DialogueSubtopic.TRANSPORT_OR_VEHICLE_SUPPORT
            elif any(keyword in logistics_text for keyword in ("fare", "taxi", "cab", "money for the ride", "money for the taxi", "spare change", "pay for the ride", "pay for the taxi")):
                subtopic = DialogueSubtopic.FARE_OR_MONEY_SUPPORT

        if subtopic is DialogueSubtopic.BACKUP_OR_STAY_NEARBY:
            return LogisticsCommitment.DECLINE_JOIN
        if subtopic is DialogueSubtopic.TRANSPORT_OR_VEHICLE_SUPPORT:
            return LogisticsCommitment.INDIRECT_SUPPORT if topic_result is TopicResult.OPENED else LogisticsCommitment.DECLINE_JOIN
        if subtopic is DialogueSubtopic.FARE_OR_MONEY_SUPPORT:
            return LogisticsCommitment.INDIRECT_SUPPORT if topic_result is TopicResult.OPENED else LogisticsCommitment.ABSOLUTE_REFUSAL

        if topic_result is TopicResult.OPENED:
            return LogisticsCommitment.INDIRECT_SUPPORT
        if topic_result is TopicResult.PARTIAL:
            return LogisticsCommitment.DECLINE_JOIN
        return LogisticsCommitment.ABSOLUTE_REFUSAL

    def _dialogue_metadata_text(self, dialogue_metadata: DialogueMetadata | None) -> str:
        if dialogue_metadata is None:
            return ""
        parts = (
            dialogue_metadata.utterance_text,
            dialogue_metadata.speech_text,
            dialogue_metadata.topic,
        )
        return " ".join(part.lower().replace("-", " ") for part in parts if part).strip()

    def _split_social_effects(self, applied_effects: tuple[str, ...]) -> tuple[tuple[str, ...], tuple[str, ...]]:
        plot_effects = tuple(
            effect
            for effect in applied_effects
            if effect in {"dialogue_plot_progressed", "dialogue_story_flag_added"}
        )
        plot_effect_set = set(plot_effects)
        state_effects = tuple(effect for effect in applied_effects if effect not in plot_effect_set)
        return state_effects, plot_effects

    def _resolve_next_conversation_subtopic(
        self,
        command: TalkCommand,
        dialogue_adjudication: DialogueAdjudicationOutcome | None,
    ) -> DialogueSubtopic | None:
        explicit_subtopic = detect_dialogue_subtopic(command.dialogue_metadata)
        if explicit_subtopic is not None:
            return explicit_subtopic
        if command.conversation_subtopic is None:
            return None
        if command.conversation_subtopic is DialogueSubtopic.MISSING_LEDGER:
            if dialogue_adjudication is None or not dialogue_adjudication.is_blocked:
                return command.conversation_subtopic
            return None
        if dialogue_adjudication is None:
            return command.conversation_subtopic
        if dialogue_adjudication.dialogue_domain in {
            DialogueDomain.OFF_TOPIC_REQUEST,
            DialogueDomain.TRAVEL_PROPOSAL,
            DialogueDomain.UNKNOWN_MISC,
        }:
            return command.conversation_subtopic
        if dialogue_adjudication.dialogue_domain in {
            DialogueDomain.LEAD_TOPIC,
            DialogueDomain.LEAD_PRESSURE,
        }:
            return None
        return command.conversation_subtopic

    def _apply_post_resolution_consequences_phase(
        self,
        command: Command,
        result: CommandResult,
        adjudication: ActionAdjudicationOutcome,
    ) -> tuple[CommandResult, ActionCheckOutcome | None, ActionConsequenceSummary]:
        if not result.render_scene or not adjudication.requires_roll:
            return result, None, ActionConsequenceSummary()

        check_outcome = self._resolve_check(command, adjudication)
        consequence_summary = apply_post_resolution_consequences(
            self._world_state,
            command,
            adjudication,
            check_outcome,
        )
        return result, check_outcome, consequence_summary

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

        update_npcs_for_current_time(self._world_state)
        self._conversation_context.sync_with_world(self._world_state)
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
            dialogue_presentation=result.dialogue_presentation,
        )

    def _classify_turn_kind(
        self,
        command: Command,
        adjudication: ActionAdjudicationOutcome,
        consequence_summary: ActionConsequenceSummary,
    ) -> TurnOutcomeKind:
        if adjudication.is_blocked:
            return TurnOutcomeKind.BLOCKED
        if adjudication.requires_roll or consequence_summary.has_applied_effects or isinstance(command, (MoveCommand, WaitCommand, TalkCommand, InvestigateCommand)):
            return TurnOutcomeKind.STATEFUL_ACTION
        return TurnOutcomeKind.NON_STATEFUL_ACTION

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
        return self._scene_provider.render_scene(self._world_state)

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
                plot.learned_outcome,
                plot.closing_beat,
            ]
        )
