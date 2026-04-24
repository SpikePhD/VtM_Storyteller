from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vampire_storyteller.action_resolution import ActionBlockReason, NormalizationSource, TurnOutcomeKind
from vampire_storyteller.dice_engine import DeterministicCheckKind
from vampire_storyteller.dice_engine import DeterministicCheckResolution
from vampire_storyteller.config import AppConfig
from vampire_storyteller.command_dispatcher import execute_command
from vampire_storyteller.command_models import ConversationStance, DialogueAct, DialogueMove, TalkCommand
from vampire_storyteller.command_result import CommandResult
from vampire_storyteller.cli import build_runtime_composition
from vampire_storyteller.conversation_context import DialogueHistoryEntry, DialogueMemoryContext
from vampire_storyteller.dialogue_adjudication import DialogueTopicStatus
from vampire_storyteller.dialogue_domain import DialogueDomain
from vampire_storyteller.dialogue_renderer import DialogueFactCard, DialogueRenderInput, DeterministicDialogueRenderer
from vampire_storyteller.dialogue_intent_adapter import DialogueIntentProposal, NullDialogueIntentAdapter, build_dialogue_intent_context
from vampire_storyteller.dialogue_subtopic import DialogueSubtopic
from vampire_storyteller.game_session import GameSession
from vampire_storyteller.models import NPCDialogueProfile
from vampire_storyteller.narrative_provider import SceneNarrativeProvider
from vampire_storyteller.social_models import LogisticsCommitment, SocialOutcomeKind, SocialOutcomePacket, SocialStanceShift, TopicResult
from vampire_storyteller.narrative_provider import DeterministicSceneNarrativeProvider
from vampire_storyteller.world_state import WorldState
from vampire_storyteller.input_interpreter import InputInterpreter


class RecordingSceneProvider(SceneNarrativeProvider):
    def __init__(self) -> None:
        self.rendered_world_times: list[str] = []

    def render_scene(self, world_state: WorldState) -> str:
        self.rendered_world_times.append(world_state.current_time)
        return f"rendered:{world_state.current_time}"


class RecordingDialogueIntentAdapter:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def propose_dialogue_intent(self, context) -> object:
        self.calls.append(context.raw_input)
        from vampire_storyteller.dialogue_intent_adapter import DialogueIntentProposal

        return DialogueIntentProposal(
            dialogue_act="ask",
            dialogue_move="continue",
            target_npc_text=context.conversation_focus_npc_name or "Jonas Reed",
            topic="missing_ledger",
            tone="curious",
        )


class RecordingElizaDialogueIntentAdapter:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def propose_dialogue_intent(self, context) -> object:
        self.calls.append(context.raw_input)
        from vampire_storyteller.dialogue_intent_adapter import DialogueIntentProposal

        return DialogueIntentProposal(
            dialogue_act="ask",
            dialogue_move="continue",
            target_npc_text="Sister Eliza",
            topic="church_records",
            tone="careful",
        )


class RecordingDialogueRenderer:
    def __init__(self) -> None:
        self.render_inputs: list[DialogueRenderInput] = []

    def render_dialogue(self, render_input: DialogueRenderInput) -> str:
        self.render_inputs.append(render_input)
        return "The church records can wait for you."


class RecordingOpenAISceneProvider:
    def render_scene(self, world_state: WorldState) -> str:
        return "OpenAI scene narration."


class RecordingOpenAIDialogueRenderer:
    def __init__(self) -> None:
        self.render_inputs: list[DialogueRenderInput] = []

    def render_dialogue(self, render_input: DialogueRenderInput) -> str:
        self.render_inputs.append(render_input)
        return "OpenAI dialogue line."


class DefaultOpenAISceneNarrativeProvider(DeterministicSceneNarrativeProvider):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__()


class DefaultOpenAIDialogueIntentAdapter:
    def __init__(self, *args, **kwargs) -> None:
        self._classifier = InputInterpreter()

    def propose_dialogue_intent(self, context) -> DialogueIntentProposal:
        normalized_text = self._classifier._normalize_text(context.raw_input)
        speech_text = context.raw_input
        normalized_speech_text = self._classifier._normalize_text(speech_text)
        dialogue_act = self._classifier._classify_dialogue_act(context.raw_input, normalized_text, speech_text, normalized_speech_text)
        dialogue_move = self._classifier._classify_dialogue_move(
            context.raw_input,
            normalized_text,
            speech_text,
            normalized_speech_text,
            dialogue_act,
        )
        if any(
            phrase in normalized_text
            for phrase in (
                "hostile",
                "repeating what i am saying",
                "you just did",
                "that sounds wrong",
            )
        ):
            dialogue_act = DialogueAct.ACCUSE
            dialogue_move = DialogueMove.CLARIFY
        target_npc_text = context.conversation_focus_npc_name or "Jonas Reed"
        topic = self._infer_topic(context.raw_input, normalized_text, dialogue_act)
        tone = self._infer_tone(dialogue_act, dialogue_move, normalized_text)
        return DialogueIntentProposal(
            dialogue_act=dialogue_act.value,
            dialogue_move=dialogue_move.value,
            target_npc_text=target_npc_text,
            topic=topic,
            tone=tone,
        )

    def _infer_topic(self, raw_input: str, normalized_text: str, dialogue_act: DialogueAct) -> str:
        if any(
            phrase in normalized_text
            for phrase in (
                "need blood",
                "give me blood",
                "feed me",
                "feed off",
                "vampire",
                "blood",
            )
        ):
            return "blood"

        if any(
            phrase in normalized_text
            for phrase in (
                "back me up",
                "backup",
                "back up",
                "watch my back",
                "cover me",
                "stay nearby",
                "stay close",
                "wait nearby",
                "wait in the car",
                "stay in the car",
            )
        ):
            return "backup"

        if any(
            phrase in normalized_text
            for phrase in (
                "spare change",
                "taxi fare",
                "cab fare",
                "money to pay",
                "money for the taxi",
                "money for the ride",
                "money for the trip",
                "pay for the taxi",
                "pay for the ride",
                "pay for the trip",
                "pay the taxi",
                "pay the fare",
                "cash for the ride",
                "cash for the trip",
                "cover the fare",
            )
        ):
            return "fare"

        if any(
            phrase in normalized_text
            for phrase in (
                "drive",
                "ride",
                "lift",
                "drop me off",
                "vehicle",
                "have a car",
                "got a car",
                "spare car",
                "transport",
            )
        ):
            return "transport"

        if any(
            phrase in normalized_text
            for phrase in (
                "ledger",
                "paper trail",
                "receipt",
                "broker",
                "waterline",
                "dock",
                "docks",
                "church records",
                "records",
                "what happened",
                "what about",
                "tell me more",
                "trail",
                "who are you",
                "what do you do",
                "more about you",
            )
        ):
            return "missing_ledger"

        if any(phrase in normalized_text for phrase in ("how are you", "hello", "hi", "hey", "good evening", "good morning", "good afternoon")):
            return "small_talk"

        if dialogue_act in {DialogueAct.ASK, DialogueAct.PERSUADE, DialogueAct.ACCUSE, DialogueAct.THREATEN}:
            return "lead_topic"

        return "conversation"

    def _infer_tone(self, dialogue_act: DialogueAct, dialogue_move: DialogueMove, normalized_text: str) -> str:
        if any(
            phrase in normalized_text
            for phrase in (
                "hostile",
                "repeating what i am saying",
                "you just did",
                "that sounds wrong",
            )
        ):
            return "guarded"
        if dialogue_act is DialogueAct.THREATEN:
            return "tense"
        if dialogue_act is DialogueAct.ACCUSE:
            return "guarded"
        if dialogue_act is DialogueAct.PERSUADE:
            return "careful"
        if dialogue_move in {DialogueMove.REACT, DialogueMove.BANTER}:
            return "warm"
        if dialogue_move is DialogueMove.CLARIFY:
            return "guarded"
        if "please" in normalized_text:
            return "polite"
        return "curious"


class DefaultOpenAIDialogueRenderer:
    def __init__(self, *args, **kwargs) -> None:
        self._renderer = DeterministicDialogueRenderer()

    def render_dialogue(self, render_input: DialogueRenderInput) -> str:
        return self._renderer.render_dialogue(render_input)


class FailingDialogueRenderer:
    def render_dialogue(self, render_input) -> str:
        raise RuntimeError("OpenAI dialogue renderer unavailable")


class GameSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._scene_patch = patch("vampire_storyteller.game_session.OpenAISceneNarrativeProvider", DefaultOpenAISceneNarrativeProvider)
        self._intent_patch = patch("vampire_storyteller.game_session.OpenAIDialogueIntentAdapter", DefaultOpenAIDialogueIntentAdapter)
        self._renderer_patch = patch("vampire_storyteller.game_session.OpenAIDialogueRenderer", DefaultOpenAIDialogueRenderer)
        self._scene_patch.start()
        self._intent_patch.start()
        self._renderer_patch.start()
        self.addCleanup(self._scene_patch.stop)
        self.addCleanup(self._intent_patch.stop)
        self.addCleanup(self._renderer_patch.stop)

    def assertDialogueFirstTalkOutput(self, result: CommandResult) -> None:
        self.assertFalse(result.render_scene)
        forbidden_fragments = (
            "Location:",
            "Exits:",
            "Active Plots:",
            "Recent Events:",
            "Rolled dialogue_social check",
            "Dialogue check success:",
            "Dialogue check failed:",
        )
        for fragment in forbidden_fragments:
            self.assertNotIn(fragment, result.output_text)

    def assertNoUnsupportedLogisticsPromise(self, output_text: str) -> None:
        normalized_output = output_text.lower()
        for banned_term in ("watch", "shadows", "nearby", "backup", "cover", "keep an eye", "wait", "drive", "escort"):
            self.assertNotIn(banned_term, normalized_output)

    def test_default_session_builds_successfully(self) -> None:
        session = GameSession()
        world = session.get_world_state()
        self.assertIsNotNone(world)
        self.assertEqual(world.player.name, "Mara Vale")
        self.assertEqual(world.player.location_id, "loc_cafe")
        self.assertEqual(world.player.hunger, 2)
        self.assertEqual(world.player.stats["strength"], 2)

    def test_startup_text_is_non_empty(self) -> None:
        session = GameSession()
        self.assertTrue(session.get_startup_text().strip())

    def test_look_returns_non_quit_result(self) -> None:
        session = GameSession()
        result = session.process_input("look")

        self.assertIsInstance(result, CommandResult)
        self.assertFalse(result.should_quit)
        self.assertTrue(result.output_text.strip())

    def test_move_updates_session_world_state(self) -> None:
        session = GameSession()
        session.process_input("move loc_church")

        world = session.get_world_state()
        self.assertEqual(world.player.location_id, "loc_church")
        self.assertEqual(world.current_time, "2026-04-09T22:08:00+02:00")

    def test_move_to_invalid_destination_returns_explicit_feedback(self) -> None:
        session = GameSession()

        result = session.process_input("move loc_missing")
        turn = session.get_last_action_resolution()

        self.assertIn("Move is blocked", result.output_text)
        self.assertIn("loc_missing", result.output_text)
        self.assertFalse(result.render_scene)
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertTrue(turn.adjudication.is_blocked)
        self.assertEqual(turn.adjudication.block_reason, ActionBlockReason.INVALID_DESTINATION)

    def test_wait_updates_hunger_and_time(self) -> None:
        session = GameSession()
        session.process_input("wait 60")

        world = session.get_world_state()
        self.assertEqual(world.current_time, "2026-04-09T23:00:00+02:00")
        self.assertEqual(world.player.hunger, 3)

    def test_quit_returns_should_quit_true(self) -> None:
        session = GameSession()
        result = session.process_input("quit")
        self.assertTrue(result.should_quit)

    def test_unsupported_freeform_input_returns_explicit_failure(self) -> None:
        session = GameSession()

        result = session.process_input("sing a song")
        normalized = session.get_last_normalized_action()

        self.assertIn("Unsupported freeform input", result.output_text)
        self.assertFalse(result.render_scene)
        self.assertIsNotNone(normalized)
        assert normalized is not None
        self.assertEqual(normalized.source, NormalizationSource.FAILED)
        self.assertIsNone(normalized.command)
        self.assertIn("no freeform interpretation rule matched", normalized.failure_reason or "")

    def test_invalid_canonical_command_returns_explicit_failure(self) -> None:
        session = GameSession()

        result = session.process_input("talk")
        normalized = session.get_last_normalized_action()

        self.assertIn("Invalid canonical command", result.output_text)
        self.assertFalse(result.render_scene)
        self.assertIsNotNone(normalized)
        assert normalized is not None
        self.assertEqual(normalized.source, NormalizationSource.FAILED)
        self.assertIsNone(normalized.command)
        self.assertIn("talk requires exactly 1 npc_id argument", normalized.failure_reason or "")

    def test_investigate_while_premature_returns_explicit_feedback(self) -> None:
        session = GameSession()

        result = session.process_input("investigate")

        self.assertIn("Investigate is blocked", result.output_text)
        self.assertIn("Missing Ledger", result.output_text)
        self.assertIn("lead_confirmed", result.output_text)
        self.assertFalse(result.render_scene)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")
        self.assertEqual(len(session.get_world_state().event_log), 0)

    def test_investigate_at_dock_before_lead_confirmed_returns_explicit_feedback(self) -> None:
        session = GameSession()

        session.process_input("move loc_church")
        session.process_input("move loc_dock")
        result = session.process_input("investigate")

        self.assertIn("Investigate is blocked", result.output_text)
        self.assertIn("lead_confirmed", result.output_text)
        self.assertFalse(result.render_scene)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "church_visited")

    def test_talk_to_present_npc_returns_stable_dialogue_result(self) -> None:
        session = GameSession()

        result = session.process_input("talk npc_1")
        normalized = session.get_last_normalized_action()
        turn = session.get_last_action_resolution()

        self.assertTrue(result.output_text.strip())
        self.assertFalse(result.render_scene)
        self.assertEqual(session.get_world_state().player.location_id, "loc_cafe")
        self.assertEqual(session.get_world_state().npcs["npc_1"].trust_level, 1)
        self.assertEqual(session.get_conversation_focus_npc_id(), "npc_1")
        self.assertEqual(session.get_conversation_stance(), ConversationStance.NEUTRAL)
        self.assertIn("trust: 1", session.get_startup_text())
        self.assertIsNotNone(normalized)
        assert normalized is not None
        self.assertEqual(normalized.source, NormalizationSource.DIRECT_COMMAND)
        self.assertEqual(normalized.canonical_command_text, "talk npc_1")
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertEqual(turn.canonical_action_text, "talk npc_1")
        self.assertEqual(turn.normalization_source, NormalizationSource.DIRECT_COMMAND)
        self.assertEqual(turn.turn_kind, TurnOutcomeKind.STATEFUL_ACTION)

    def test_talk_greeting_uses_dialogue_metadata(self) -> None:
        session = GameSession()

        result = session.process_input("Jonas, good evening.")
        turn = session.get_last_action_resolution()

        self.assertEqual(result.output_text, "Evening.")
        self.assertIsNotNone(result.dialogue_presentation)
        assert result.dialogue_presentation is not None
        self.assertEqual(result.dialogue_presentation.player_utterance, "good evening.")
        self.assertEqual(result.dialogue_presentation.npc_display_name, "Jonas Reed")
        self.assertTrue(result.dialogue_presentation.focus_changed)
        self.assertEqual(session.get_world_state().npcs["npc_1"].trust_level, 0)
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertEqual(turn.normalization_source, NormalizationSource.INTERPRETED)
        self.assertEqual(turn.canonical_action_text, "talk npc_1")
        self.assertEqual(turn.turn_kind, TurnOutcomeKind.STATEFUL_ACTION)

    def test_follow_up_uses_conversation_focus(self) -> None:
        session = GameSession()

        session.process_input("Jonas, good evening.")
        result = session.process_input("Why?")
        interpreted = session.get_last_interpreted_input()

        self.assertTrue(result.output_text.strip())
        self.assertNotIn("go on", result.output_text.lower())
        self.assertNotIn("i'm listening", result.output_text.lower())
        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertEqual(interpreted.dialogue_metadata.dialogue_act, DialogueAct.ASK)
        self.assertEqual(session.get_conversation_focus_npc_id(), "npc_1")

    def test_pronoun_follow_up_reuses_conversation_focus(self) -> None:
        session = GameSession()

        session.process_input("Jonas, good evening.")
        result = session.process_input("I turn back to her and continue.")
        interpreted = session.get_last_interpreted_input()

        self.assertTrue(result.output_text.strip())
        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertEqual(session.get_conversation_focus_npc_id(), "npc_1")

    def test_follow_up_unknownish_line_still_targets_focus(self) -> None:
        session = GameSession()

        session.process_input("Jonas, good evening.")
        result = session.process_input("I don't believe you.")
        interpreted = session.get_last_interpreted_input()
        turn = session.get_last_action_resolution()

        self.assertTrue(result.output_text.strip())
        self.assertNotIn("go on", result.output_text.lower())
        self.assertNotIn("i'm listening", result.output_text.lower())
        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertEqual(interpreted.dialogue_metadata.dialogue_act, DialogueAct.ACCUSE)
        self.assertEqual(session.get_world_state().story_flags, [])
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")
        self.assertEqual(session.get_conversation_stance(), ConversationStance.GUARDED)
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertIsNotNone(turn.dialogue_adjudication)
        assert turn.dialogue_adjudication is not None
        self.assertTrue(turn.dialogue_adjudication.is_guarded)

    def test_recent_dialogue_history_records_and_trims_to_bounded_window(self) -> None:
        session = GameSession()

        session.process_input("Jonas, good evening.")
        for _ in range(6):
            session.process_input("Jonas, hello again.")

        history = session.get_recent_dialogue_history()

        self.assertLessEqual(len(history), 12)
        self.assertEqual(len(history), 12)
        self.assertEqual(history[-1].speaker, "Jonas Reed")
        self.assertNotEqual(history[0].utterance_text, "good evening.")

    def test_recent_dialogue_history_keeps_player_and_npc_lines(self) -> None:
        session = GameSession()

        session.process_input("Jonas, hello.")
        history = session.get_recent_dialogue_history()

        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].speaker, "player")
        self.assertEqual(history[0].utterance_text, "hello.")
        self.assertEqual(history[1].speaker, "Jonas Reed")
        self.assertTrue(history[1].utterance_text.strip())

    def test_live_dialogue_render_context_receives_memory_layers(self) -> None:
        renderer = RecordingDialogueRenderer()
        session = GameSession(dialogue_renderer=renderer)

        session.process_input("Jonas, good evening.")
        session.process_input("What is going on, how are you?")

        self.assertGreaterEqual(len(renderer.render_inputs), 2)
        render_input = renderer.render_inputs[-1]
        self.assertIsNotNone(render_input.npc_dossier)
        assert render_input.npc_dossier is not None
        self.assertEqual(render_input.npc_dossier.public_persona, "a wary neighborhood informant who keeps public conversations short")
        self.assertIn("greeted Jonas", render_input.conversation_memory.previous_interactions_summary)
        self.assertGreaterEqual(len(render_input.conversation_memory.recent_dialogue_history), 3)
        self.assertEqual(render_input.conversation_memory.recent_dialogue_history[0].speaker, "player")

    def test_movement_clears_active_conversation_and_writes_compact_npc_memory(self) -> None:
        session = GameSession()
        world = session.get_world_state()
        world.npcs["npc_1"].previous_interactions_summary = ""

        session.process_input("Jonas, tell me exactly where the missing ledger is hidden under the red awning.")
        flags_before_move = list(world.story_flags)
        social_state_before_move = (
            world.npcs["npc_1"].social_state.trust,
            world.npcs["npc_1"].social_state.hostility,
            world.npcs["npc_1"].social_state.willingness_to_cooperate,
            world.npcs["npc_1"].social_state.current_conversation_stance,
        )

        result = session.process_input("move loc_church")
        summary = world.npcs["npc_1"].previous_interactions_summary

        self.assertTrue(result.render_scene)
        self.assertIsNone(session.get_conversation_focus_npc_id())
        self.assertEqual(session.get_recent_dialogue_history(), ())
        self.assertTrue(summary)
        self.assertLessEqual(len(summary), 220)
        self.assertIn("Mara Vale last spoke with Jonas Reed", summary)
        self.assertIn("memory_only_no_authority", summary)
        self.assertNotIn("exactly where the missing ledger is hidden under the red awning", summary)
        self.assertEqual(world.story_flags, flags_before_move)
        self.assertEqual(
            (
                world.npcs["npc_1"].social_state.trust,
                world.npcs["npc_1"].social_state.hostility,
                world.npcs["npc_1"].social_state.willingness_to_cooperate,
                world.npcs["npc_1"].social_state.current_conversation_stance,
            ),
            social_state_before_move,
        )

    def test_written_conversation_memory_is_visible_to_dialogue_intent_context(self) -> None:
        session = GameSession()
        world = session.get_world_state()
        world.npcs["npc_1"].previous_interactions_summary = ""

        session.process_input("Jonas, tell me about the dock ledger.")
        session.process_input("move loc_church")
        world.player.location_id = "loc_cafe"

        context = build_dialogue_intent_context(world, "What did Jonas say before?", "npc_1")

        self.assertEqual(
            context.conversation_memory.previous_interactions_summary,
            world.npcs["npc_1"].previous_interactions_summary,
        )
        self.assertIn("Mara Vale last spoke with Jonas Reed", context.conversation_memory.previous_interactions_summary)

    def test_switching_talk_focus_writes_memory_for_previous_npc(self) -> None:
        session = GameSession()
        world = session.get_world_state()
        world.npcs["npc_1"].previous_interactions_summary = ""
        world.npcs["npc_2"].location_id = world.player.location_id

        session.process_input("Jonas, hello.")
        result = session.process_input("talk npc_2")

        self.assertTrue(world.npcs["npc_1"].previous_interactions_summary)
        self.assertIn("Mara Vale last spoke with Jonas Reed", world.npcs["npc_1"].previous_interactions_summary)
        self.assertEqual(session.get_conversation_focus_npc_id(), "npc_2")
        self.assertEqual(result.conversation_focus_npc_id, "npc_2")

    def test_meta_conversation_stance_challenge_uses_distinct_domain(self) -> None:
        session = GameSession()

        session.process_input("Jonas, hello.")
        result = session.process_input("Why are you so hostile?")
        interpreted = session.get_last_interpreted_input()
        turn = session.get_last_action_resolution()

        self.assertNotIn("paper trail", result.output_text.lower())
        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertIsNotNone(turn.dialogue_adjudication)
        assert turn.dialogue_adjudication is not None
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.LEAD_PRESSURE)
        self.assertIn(turn.dialogue_adjudication.topic_status, {DialogueTopicStatus.AVAILABLE, DialogueTopicStatus.REFUSED, DialogueTopicStatus.PRODUCTIVE})

    def test_meta_conversation_challenge_does_not_reveal_protected_facts(self) -> None:
        session = GameSession()

        session.process_input("Jonas, hello.")
        session.process_input("Why are you so hostile?")
        turn = session.get_last_action_resolution()

        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertIsNotNone(turn.dialogue_adjudication)
        assert turn.dialogue_adjudication is not None
        self.assertNotEqual(turn.dialogue_adjudication.social_outcome.topic_result, TopicResult.OPENED)
        self.assertNotEqual(turn.dialogue_adjudication.social_outcome.outcome_kind, SocialOutcomeKind.REVEAL)

    def test_follow_up_what_do_you_mean_stays_in_question_path(self) -> None:
        session = GameSession()

        session.process_input("Jonas, good evening.")
        result = session.process_input("What do you mean?")
        interpreted = session.get_last_interpreted_input()

        self.assertTrue(result.output_text.strip())
        self.assertNotIn("go on", result.output_text.lower())
        self.assertNotIn("i'm listening", result.output_text.lower())
        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertEqual(interpreted.dialogue_metadata.dialogue_act, DialogueAct.ASK)
        self.assertEqual(session.get_conversation_stance(), ConversationStance.NEUTRAL)

    def test_content_topic_question_still_uses_the_lead_lane(self) -> None:
        session = GameSession()

        session.process_input("Jonas, hello.")
        result = session.process_input("Why are the docks the starting place?")
        turn = session.get_last_action_resolution()

        self.assertTrue(result.output_text.strip())
        self.assertNotIn("go on", result.output_text.lower())
        self.assertNotIn("i'm listening", result.output_text.lower())
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertIsNotNone(turn.dialogue_adjudication)
        assert turn.dialogue_adjudication is not None
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.LEAD_TOPIC)

    def test_background_follow_up_after_greeting_stays_with_jonas(self) -> None:
        session = GameSession()

        session.process_input("Hello Jonas, how's going?")
        result = session.process_input("Tell me more about you, what do you do?")
        interpreted = session.get_last_interpreted_input()

        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertIn("stay out of anybody's pocket", result.output_text.lower())
        self.assertNotIn("paper trail", result.output_text.lower())

    def test_statement_style_acknowledgement_uses_react_move_without_echoing_player_text(self) -> None:
        session = GameSession()

        session.process_input("Hello Jonas.")
        result = session.process_input("Just coming to say hi.")
        interpreted = session.get_last_interpreted_input()
        turn = session.get_last_action_resolution()

        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertEqual(interpreted.dialogue_metadata.dialogue_move, DialogueMove.REACT)
        self.assertIn(
            result.output_text.lower(),
            {"evening.", "all right.", "noted.", "fair enough.", "i'm holding up."},
        )
        self.assertNotIn("coming to say hi", result.output_text.lower())
        self.assertNotIn("?", result.output_text)
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertIsNotNone(turn.dialogue_adjudication)

    def test_statement_style_continuation_uses_continue_move_without_echoing_player_text(self) -> None:
        session = GameSession()

        session.process_input("Jonas, what happened at the dock?")
        result = session.process_input("Sure. Tell me.")
        interpreted = session.get_last_interpreted_input()
        turn = session.get_last_action_resolution()

        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertEqual(interpreted.dialogue_metadata.dialogue_move, DialogueMove.CONTINUE)
        self.assertNotIn("sure. tell me", result.output_text.lower())
        self.assertNotIn("go on", result.output_text.lower())
        self.assertNotIn("i'm listening", result.output_text.lower())
        self.assertTrue(result.output_text.strip())
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertIsNotNone(turn.dialogue_adjudication)

    def test_statement_style_clarify_uses_clarify_move_without_revealing_content(self) -> None:
        session = GameSession()

        session.process_input("Jonas, hello.")
        result = session.process_input("You just did.")
        interpreted = session.get_last_interpreted_input()
        turn = session.get_last_action_resolution()

        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertEqual(interpreted.dialogue_metadata.dialogue_move, DialogueMove.CLARIFY)
        self.assertNotIn("paper trail", result.output_text.lower())
        self.assertNotIn("you just did", result.output_text.lower())
        self.assertNotIn("?", result.output_text)
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertIsNotNone(turn.dialogue_adjudication)

    def test_statement_style_banter_uses_banter_move_without_echoing_player_text(self) -> None:
        session = GameSession()

        session.process_input("Jonas, hello.")
        result = session.process_input("There you are! anyhow, I know you have information for me.")
        interpreted = session.get_last_interpreted_input()
        turn = session.get_last_action_resolution()

        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertEqual(interpreted.dialogue_metadata.dialogue_move, DialogueMove.BANTER)
        self.assertNotIn("there you are", result.output_text.lower())
        self.assertTrue(result.output_text.strip())
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertIsNotNone(turn.dialogue_adjudication)

    def test_meta_question_uses_clarify_move_without_echoing_player_text(self) -> None:
        session = GameSession()

        session.process_input("Jonas, hello.")
        result = session.process_input("Are you repeating what I am saying?")
        interpreted = session.get_last_interpreted_input()
        turn = session.get_last_action_resolution()

        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertEqual(interpreted.dialogue_metadata.dialogue_move, DialogueMove.CLARIFY)
        self.assertNotIn("repeating what i am saying", result.output_text.lower())
        self.assertTrue(result.output_text.strip())
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertIsNotNone(turn.dialogue_adjudication)

    def test_statement_style_meta_looping_keeps_jonas_focused_without_echoing_or_questioning(self) -> None:
        session = GameSession()

        session.process_input("Jonas, hello.")
        result = session.process_input("You are looping.")
        interpreted = session.get_last_interpreted_input()
        turn = session.get_last_action_resolution()

        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertEqual(interpreted.dialogue_metadata.dialogue_move, DialogueMove.CLARIFY)
        self.assertNotIn("you are looping", result.output_text.lower())
        self.assertNotIn("?", result.output_text)
        self.assertTrue(result.output_text.strip())
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertIsNotNone(turn.dialogue_adjudication)

    def test_statement_style_observation_line_stays_in_dialogue_without_echoing_or_questioning(self) -> None:
        session = GameSession()

        session.process_input("Jonas, hello.")
        result = session.process_input("Sounds like this is more than just a missing ledger.")
        interpreted = session.get_last_interpreted_input()
        turn = session.get_last_action_resolution()

        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertIn(interpreted.dialogue_metadata.dialogue_move, {DialogueMove.REACT, DialogueMove.CLARIFY})
        self.assertNotIn("sounds like this is more than just a missing ledger", result.output_text.lower())
        self.assertNotIn("?", result.output_text)
        self.assertTrue(result.output_text.strip())
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertIsNotNone(turn.dialogue_adjudication)

    def test_active_conversation_declarative_line_routes_into_dialogue_intent_by_default(self) -> None:
        adapter = RecordingDialogueIntentAdapter()
        session = GameSession(dialogue_intent_adapter=adapter)

        session.process_input("Jonas, good evening.")
        result = session.process_input("Busy - got into a job that I did not really want to do")
        interpreted = session.get_last_interpreted_input()
        turn = session.get_last_action_resolution()

        self.assertNotIn("Unsupported freeform input", result.output_text)
        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertIsNotNone(interpreted.dialogue_metadata)
        assert interpreted.dialogue_metadata is not None
        self.assertEqual(interpreted.dialogue_metadata.dialogue_act, DialogueAct.ASK)
        self.assertEqual(interpreted.dialogue_metadata.dialogue_move, DialogueMove.CONTINUE)
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertIsNotNone(turn.dialogue_adjudication)
        self.assertIsNotNone(result.dialogue_presentation)
        self.assertGreaterEqual(len(adapter.calls), 1)
        self.assertIn("Busy - got into a job that I did not really want to do", adapter.calls[-1])

    def test_active_conversation_pressure_lines_fall_back_when_adapter_is_unusable(self) -> None:
        session = GameSession(dialogue_intent_adapter=NullDialogueIntentAdapter())

        session.process_input("Jonas, hello.")
        first_result = session.process_input("But I need your help.")
        first_interpreted = session.get_last_interpreted_input()
        second_result = session.process_input("Listen I don't have time for this. What do you know")
        second_interpreted = session.get_last_interpreted_input()

        self.assertFalse(first_result.render_scene)
        self.assertFalse(second_result.render_scene)
        self.assertEqual(first_interpreted.target_reference, "npc_1")
        self.assertEqual(second_interpreted.target_reference, "npc_1")
        self.assertEqual(first_interpreted.dialogue_metadata.dialogue_move, DialogueMove.CONTINUE)
        self.assertEqual(second_interpreted.dialogue_metadata.dialogue_move, DialogueMove.CONTINUE)
        self.assertEqual(first_interpreted.dialogue_metadata.dialogue_act, DialogueAct.PERSUADE)
        self.assertIn(second_interpreted.dialogue_metadata.dialogue_act, {DialogueAct.ASK, DialogueAct.UNKNOWN})
        self.assertTrue(first_result.output_text.strip())
        self.assertTrue(second_result.output_text.strip())
        self.assertIsNone(first_interpreted.failure_reason)
        self.assertIsNone(second_interpreted.failure_reason)

    def test_active_conversation_explicit_world_action_stays_on_existing_path(self) -> None:
        adapter = RecordingDialogueIntentAdapter()
        session = GameSession(dialogue_intent_adapter=adapter)

        session.process_input("Jonas, good evening.")
        result = session.process_input("look around the cafe")
        interpreted = session.get_last_interpreted_input()

        self.assertTrue(result.render_scene)
        self.assertEqual(interpreted.normalized_intent, "look")
        self.assertEqual(interpreted.canonical_command, "look")
        self.assertEqual(adapter.calls, [])

    def test_dialogue_rendering_support_no_longer_depends_on_jonas_id(self) -> None:
        session = GameSession()
        render_input = DialogueRenderInput(
            npc_id="npc_2",
            npc_name="Sister Eliza",
            npc_role="Observer",
            player_name="Mara Vale",
            location_name="Blackthorn Cafe",
            utterance_text="Sister Eliza, what happened here?",
            speech_text="what happened here?",
            dialogue_act="ask",
            dialogue_domain="lead_topic",
            topic_status="productive",
            adjudication_resolution_kind="allowed",
            conversation_stance="neutral",
            conversation_subtopic=None,
            continuity_cue=None,
            npc_trust_level=0,
            plot_name="Missing Ledger",
            plot_stage="hook",
            lead_flag_active=False,
            check_kind=None,
            check_is_success=None,
            check_successes=None,
            check_difficulty=None,
            consequence_messages=(),
            applied_effects=(),
            npc_profile=NPCDialogueProfile(
                background_summary="Sister Eliza protects records and people.",
                public_persona="a guarded haven keeper",
                private_history_summary="She does not give much away.",
                motivations=["protect the church records"],
                speaking_style="measured and restrained",
                relationship_context="She is cautious with Mara.",
            ),
            npc_dossier=None,
            conversation_memory=DialogueMemoryContext(
                previous_interactions_summary="Mara has already visited the church once.",
                recent_dialogue_history=(
                    DialogueHistoryEntry(speaker="player", utterance_text="Hello."),
                ),
            ),
            authorized_fact_cards=(
                DialogueFactCard(
                    fact_id="test_fact",
                    kind="background",
                    summary="She stays measured and keeps her answer narrow.",
                ),
            ),
            social_outcome=SocialOutcomePacket(
                outcome_kind=SocialOutcomeKind.COOPERATE,
                stance_shift=SocialStanceShift(
                    from_stance=ConversationStance.NEUTRAL,
                    to_stance=ConversationStance.NEUTRAL,
                ),
                check_required=False,
                check_result=None,
                topic_result=TopicResult.UNCHANGED,
                state_effects=(),
                plot_effects=(),
                reason_code="test_packet",
            ),
        )

        self.assertTrue(session._supports_dialogue_rendering(render_input))

    def test_dialogue_rendering_runtime_failure_hard_fails_the_turn(self) -> None:
        session = GameSession(dialogue_renderer=FailingDialogueRenderer())

        result = session.process_input("Jonas, what happened at the dock?")

        self.assertIn("dialogue rendering failed", result.output_text.lower())
        self.assertIn("openai dialogue renderer unavailable", result.output_text.lower())
        self.assertFalse(result.render_scene)

    def test_eliza_church_records_slice_routes_through_the_same_architecture(self) -> None:
        adapter = RecordingElizaDialogueIntentAdapter()
        renderer = RecordingDialogueRenderer()
        session = GameSession(dialogue_intent_adapter=adapter, dialogue_renderer=renderer)

        session.process_input("move loc_church")
        session.process_input("Sister Eliza, good evening.")
        result = session.process_input("What about the church records?")
        turn = session.get_last_action_resolution()

        self.assertEqual(result.output_text, "The church records can wait for you.")
        self.assertIsNotNone(result.dialogue_presentation)
        self.assertGreaterEqual(len(adapter.calls), 1)
        self.assertGreaterEqual(len(renderer.render_inputs), 2)
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertIsNotNone(turn.dialogue_adjudication)
        assert turn.dialogue_adjudication is not None
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.LEAD_TOPIC)
        self.assertEqual(turn.dialogue_adjudication.topic_status, DialogueTopicStatus.PRODUCTIVE)
        last_render_input = renderer.render_inputs[-1]
        self.assertEqual(last_render_input.npc_name, "Sister Eliza")
        self.assertIn("eliza_church_records_lead", [fact.fact_id for fact in last_render_input.authorized_fact_cards])
        self.assertIn("eliza_church_records_follow_up", [fact.fact_id for fact in last_render_input.authorized_fact_cards])
        self.assertNotIn("Unsupported freeform input", result.output_text)

    def test_full_openai_storyteller_session_uses_non_deterministic_components(self) -> None:
        with patch("vampire_storyteller.cli.OpenAISceneNarrativeProvider", return_value=RecordingOpenAISceneProvider()) as mock_scene_ctor:
            with patch("vampire_storyteller.cli.OpenAIDialogueIntentAdapter", return_value=RecordingDialogueIntentAdapter()) as mock_intent_ctor:
                with patch("vampire_storyteller.cli.OpenAIDialogueRenderer", return_value=RecordingOpenAIDialogueRenderer()) as mock_renderer_ctor:
                    runtime = build_runtime_composition(
                        AppConfig(
                            openai_api_key="test-key",
                            openai_model="gpt-4.1-mini",
                        )
                    )

        self.assertEqual(runtime.mode_label, "OpenAI storyteller")
        self.assertEqual(runtime.dialogue_render_label, "OpenAI")
        self.assertEqual(runtime.notices, ())
        self.assertNotIsInstance(runtime.scene_provider, DeterministicSceneNarrativeProvider)
        mock_scene_ctor.assert_called_once_with(api_key="test-key", model="gpt-4.1-mini")
        mock_intent_ctor.assert_called_once_with(api_key="test-key", model="gpt-4.1-mini")
        mock_renderer_ctor.assert_called_once_with(api_key="test-key", model="gpt-4.1-mini")

        session = GameSession(
            scene_provider=runtime.scene_provider,
            dialogue_intent_adapter=runtime.dialogue_intent_adapter,
            dialogue_renderer=runtime.dialogue_renderer,
        )
        startup_text = session.get_startup_text()
        self.assertIn("OpenAI scene narration.", startup_text)
        self.assertNotIn("deterministic", startup_text.lower())

    def test_missing_ledger_follow_up_stays_in_the_same_subtopic(self) -> None:
        session = GameSession()

        session.process_input("Jonas, what happened at the dock?")
        result = session.process_input("What about it")
        interpreted = session.get_last_interpreted_input()
        turn = session.get_last_action_resolution()

        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertEqual(turn.canonical_action_text, "talk npc_1")
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.LEAD_TOPIC)
        self.assertEqual(session.get_conversation_focus_npc_id(), "npc_1")
        self.assertEqual(session.get_conversation_subtopic(), DialogueSubtopic.MISSING_LEDGER)
        self.assertNotIn("Unsupported freeform input", result.output_text)

    def test_guarded_follow_up_does_not_upgrade_missing_ledger_lane(self) -> None:
        session = GameSession()

        session.process_input("Jonas, what happened at the dock?")
        result = session.process_input("I don't believe you.")
        turn = session.get_last_action_resolution()

        self.assertEqual(turn.canonical_action_text, "talk npc_1")
        self.assertEqual(turn.dialogue_adjudication.topic_status, DialogueTopicStatus.REFUSED)
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.LEAD_PRESSURE)
        self.assertEqual(session.get_conversation_subtopic(), DialogueSubtopic.MISSING_LEDGER)
        self.assertTrue(
            "not naming names" in result.output_text.lower()
            or "guarded" in result.output_text.lower()
        )

    def test_guarded_refusal_keeps_focus_for_prove_it_follow_up(self) -> None:
        session = GameSession()

        session.process_input("Hello Jonas")
        session.process_input("That sounds heavier than usual. Someone got you looking over your shoulder?")
        session.process_input("Then give me the short version. What happened at the docks?")
        session.process_input("You’re not keeping quiet for my sake. You’re scared. Of who?")
        result = session.process_input('Fine. What does "prove it" look like to you?')
        turn = session.get_last_action_resolution()

        self.assertNotIn("could not identify a valid NPC", result.output_text.lower())
        self.assertEqual(session.get_conversation_focus_npc_id(), "npc_1")
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertIsNotNone(turn.dialogue_adjudication)
        assert turn.dialogue_adjudication is not None
        self.assertEqual(turn.conversation_focus_npc_id, "npc_1")
        self.assertIn(turn.dialogue_adjudication.dialogue_domain, {DialogueDomain.LEAD_TOPIC, DialogueDomain.LEAD_PRESSURE})

    def test_backup_follow_up_stays_in_dialogue_without_repeating_name(self) -> None:
        session = GameSession()

        session.process_input("Jonas, good evening.")
        result = session.process_input("I need you as a back up")
        interpreted = session.get_last_interpreted_input()
        turn = session.get_last_action_resolution()

        self.assertIn("not go with you", result.output_text.lower())
        self.assertNoUnsupportedLogisticsPromise(result.output_text)
        self.assertNotIn("Unsupported freeform input", result.output_text)
        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertEqual(turn.canonical_action_text, "talk npc_1")
        self.assertNotEqual(turn.social_outcome.logistics_commitment, LogisticsCommitment.NONE)
        self.assertNotEqual(turn.social_outcome.logistics_commitment, LogisticsCommitment.HIDDEN_SUPPORT)
        self.assertIn(
            turn.social_outcome.logistics_commitment,
            {
                LogisticsCommitment.DECLINE_JOIN,
                LogisticsCommitment.INDIRECT_SUPPORT,
                LogisticsCommitment.ABSOLUTE_REFUSAL,
            },
        )
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")
        self.assertEqual(session.get_world_state().story_flags, [])

    def test_acknowledged_backup_follow_up_stays_in_dialogue_without_repeating_name(self) -> None:
        session = GameSession()

        session.process_input("Jonas, what happened at the dock?")
        result = session.process_input("Yes we are. But I need you to back me up")
        interpreted = session.get_last_interpreted_input()
        turn = session.get_last_action_resolution()

        self.assertIn("not go with you", result.output_text.lower())
        self.assertNoUnsupportedLogisticsPromise(result.output_text)
        self.assertNotIn("Unsupported freeform input", result.output_text)
        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertEqual(turn.canonical_action_text, "talk npc_1")
        self.assertNotEqual(turn.social_outcome.logistics_commitment, LogisticsCommitment.NONE)
        self.assertNotEqual(turn.social_outcome.logistics_commitment, LogisticsCommitment.HIDDEN_SUPPORT)
        self.assertIn(
            turn.social_outcome.logistics_commitment,
            {
                LogisticsCommitment.DECLINE_JOIN,
                LogisticsCommitment.INDIRECT_SUPPORT,
                LogisticsCommitment.ABSOLUTE_REFUSAL,
            },
        )
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")
        self.assertEqual(session.get_world_state().story_flags, [])

    def test_named_backup_variant_still_works(self) -> None:
        session = GameSession()

        result = session.process_input("Jonas, I need you as a back up")
        turn = session.get_last_action_resolution()

        self.assertIn("not go with you", result.output_text.lower())
        self.assertNoUnsupportedLogisticsPromise(result.output_text)
        self.assertNotEqual(turn.social_outcome.logistics_commitment, LogisticsCommitment.NONE)
        self.assertNotEqual(turn.social_outcome.logistics_commitment, LogisticsCommitment.HIDDEN_SUPPORT)
        self.assertIn(
            turn.social_outcome.logistics_commitment,
            {
                LogisticsCommitment.DECLINE_JOIN,
                LogisticsCommitment.INDIRECT_SUPPORT,
                LogisticsCommitment.ABSOLUTE_REFUSAL,
            },
        )
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")
        self.assertEqual(session.get_world_state().story_flags, [])

    def test_taxi_spare_change_follow_up_stays_in_dialogue_without_reusing_dock_lead(self) -> None:
        session = GameSession()

        session.process_input("talk npc_1")
        session.process_input("talk npc_1")
        plot_stage_before = session.get_world_state().plots["plot_1"].stage
        story_flags_before = list(session.get_world_state().story_flags)
        result = session.process_input("Ok then. I will call the taxi - do you have some spare change?")
        interpreted = session.get_last_interpreted_input()
        turn = session.get_last_action_resolution()

        self.assertIn("not financing the ride", result.output_text.lower())
        self.assertNotIn("paper trail began", result.output_text.lower())
        self.assertNotIn("dock is the only place worth checking", result.output_text.lower())
        self.assertNotIn("Unsupported freeform input", result.output_text)
        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertEqual(turn.canonical_action_text, "talk npc_1")
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.OFF_TOPIC_REQUEST)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, plot_stage_before)
        self.assertEqual(session.get_world_state().story_flags, story_flags_before)

    def test_taxi_money_follow_up_stays_in_dialogue_without_reusing_dock_lead(self) -> None:
        session = GameSession()

        session.process_input("talk npc_1")
        session.process_input("talk npc_1")
        plot_stage_before = session.get_world_state().plots["plot_1"].stage
        story_flags_before = list(session.get_world_state().story_flags)
        result = session.process_input("I don't have money to pay for the taxi to the dock!")
        interpreted = session.get_last_interpreted_input()
        turn = session.get_last_action_resolution()

        self.assertIn("not financing the ride", result.output_text.lower())
        self.assertNotIn("paper trail began", result.output_text.lower())
        self.assertNotIn("dock is the only place worth checking", result.output_text.lower())
        self.assertNotIn("Unsupported freeform input", result.output_text)
        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertEqual(turn.canonical_action_text, "talk npc_1")
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.OFF_TOPIC_REQUEST)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, plot_stage_before)
        self.assertEqual(session.get_world_state().story_flags, story_flags_before)

    def test_blood_refusal_follow_up_stays_in_off_topic_lane(self) -> None:
        session = GameSession()

        session.process_input("Jonas, I need blood before I go")
        plot_stage_before = session.get_world_state().plots["plot_1"].stage
        story_flags_before = list(session.get_world_state().story_flags)
        result = session.process_input("Why not - are you not eager to please a vampire?")
        turn = session.get_last_action_resolution()

        self.assertNotIn("dock is the only place worth checking", result.output_text.lower())
        self.assertNotIn("paper trail began", result.output_text.lower())
        self.assertIn("ask someone else", result.output_text.lower())
        self.assertEqual(turn.canonical_action_text, "talk npc_1")
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.OFF_TOPIC_REQUEST)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, plot_stage_before)
        self.assertEqual(session.get_world_state().story_flags, story_flags_before)

    def test_feed_persuade_follow_up_does_not_return_dock_lead(self) -> None:
        session = GameSession()

        result = session.process_input("I persuade Jonas into letting me feed off him")
        turn = session.get_last_action_resolution()

        self.assertNotIn("dock is the only place worth checking", result.output_text.lower())
        self.assertNotIn("paper trail began", result.output_text.lower())
        self.assertTrue("ask someone else" in result.output_text.lower() or "refuses" in result.output_text.lower())
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.OFF_TOPIC_REQUEST)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")
        self.assertEqual(session.get_world_state().story_flags, [])

    def test_transport_vehicle_question_stays_in_logistics_lane(self) -> None:
        session = GameSession()

        result = session.process_input("Jonas do you drive?")
        turn = session.get_last_action_resolution()

        self.assertTrue(
            any(
                phrase in result.output_text.lower()
                for phrase in ("not driving you", "indirectly", "absolutely not", "not in person")
            )
        )
        self.assertNotIn("dock is the only place worth checking", result.output_text.lower())
        self.assertNotEqual(turn.social_outcome.logistics_commitment, LogisticsCommitment.NONE)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")
        self.assertEqual(session.get_world_state().story_flags, [])

    def test_spare_car_follow_up_stays_in_transport_subtopic(self) -> None:
        session = GameSession()

        session.process_input("Jonas do you drive?")
        plot_stage_before = session.get_world_state().plots["plot_1"].stage
        story_flags_before = list(session.get_world_state().story_flags)
        result = session.process_input("Do you have a spare car?")
        turn = session.get_last_action_resolution()

        self.assertTrue(
            any(
                phrase in result.output_text.lower()
                for phrase in ("not driving you", "indirectly", "absolutely not", "not in person")
            )
        )
        self.assertNotIn("dock is the only place worth checking", result.output_text.lower())
        self.assertEqual(turn.canonical_action_text, "talk npc_1")
        self.assertNotEqual(turn.social_outcome.logistics_commitment, LogisticsCommitment.NONE)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, plot_stage_before)
        self.assertEqual(session.get_world_state().story_flags, story_flags_before)

    def test_short_please_follow_up_inherits_transport_subtopic(self) -> None:
        session = GameSession()

        session.process_input("Jonas do you drive?")
        result = session.process_input("Please?")
        turn = session.get_last_action_resolution()

        self.assertNotIn("dock is the only place worth checking", result.output_text.lower())
        self.assertEqual(turn.canonical_action_text, "talk npc_1")
        self.assertNotEqual(turn.social_outcome.logistics_commitment, LogisticsCommitment.NONE)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")
        self.assertEqual(session.get_world_state().story_flags, [])

    def test_explicit_return_to_dock_restores_productive_lead_lane_after_transport(self) -> None:
        session = GameSession()

        session.process_input("Jonas do you drive?")
        result = session.process_input("What happened at the dock?")
        turn = session.get_last_action_resolution()

        self.assertIn("dock", result.output_text.lower())
        self.assertIn("paper trail", result.output_text.lower())
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.LEAD_TOPIC)

    def test_guarded_follow_up_go_on_does_not_unlock_productive_progression(self) -> None:
        session = GameSession()

        session.process_input("Jonas, good evening.")
        session.process_input("I don't believe you.")
        result = session.process_input("Go on.")

        self.assertNotIn("paper trail", result.output_text.lower())
        self.assertNotIn("go on", result.output_text.lower())
        self.assertNotIn("i'm listening", result.output_text.lower())
        self.assertNotIn("advanced from hook to lead_confirmed", result.output_text)
        self.assertEqual(session.get_world_state().story_flags, [])
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")
        self.assertEqual(session.get_conversation_stance(), ConversationStance.GUARDED)

    def test_clear_non_dialogue_action_is_not_swallowed_by_active_conversation(self) -> None:
        session = GameSession()

        session.process_input("Jonas, good evening.")
        result = session.process_input("I move to the church.")

        self.assertTrue(result.render_scene)
        self.assertEqual(session.get_world_state().player.location_id, "loc_church")

    def test_talk_question_uses_preserved_utterance_text(self) -> None:
        session = GameSession()

        result = session.process_input("I ask Jonas what happened here.")
        interpreted = session.get_last_interpreted_input()

        self.assertIsNotNone(interpreted)
        self.assertIsNotNone(interpreted.dialogue_metadata)
        self.assertIn("I ask Jonas what happened here.", interpreted.dialogue_metadata.utterance_text)
        self.assertIn("start with the dock", result.output_text.lower())
        self.assertEqual(session.get_world_state().npcs["npc_1"].trust_level, 0)

    def test_aggressive_talk_is_guarded(self) -> None:
        session = GameSession()

        accuse_result = session.process_input("I accuse Jonas of hiding something.")
        threaten_result = session.process_input("I threaten Jonas to talk.")
        threaten_turn = session.get_last_action_resolution()

        self.assertIn("guarded", accuse_result.output_text.lower())
        self.assertTrue(
            "guarded" in threaten_result.output_text.lower()
            or "keep this professional" in threaten_result.output_text.lower()
            or "watch your tone" in threaten_result.output_text.lower()
        )
        self.assertNotIn("said what he will say", threaten_result.output_text)
        self.assertIsNotNone(threaten_turn)
        assert threaten_turn is not None
        self.assertIsNotNone(threaten_turn.dialogue_adjudication)
        assert threaten_turn.dialogue_adjudication is not None
        self.assertTrue(threaten_turn.dialogue_adjudication.is_guarded)
        self.assertEqual(session.get_world_state().npcs["npc_1"].trust_level, 0)

    def test_persuade_routes_into_deterministic_social_check_and_advances_on_success(self) -> None:
        session = GameSession()

        with patch("vampire_storyteller.game_session.resolve_deterministic_check") as mock_resolve:
            mock_resolve.return_value = DeterministicCheckResolution(
                kind=DeterministicCheckKind.DIALOGUE_SOCIAL,
                seed="2026-04-09T22:00:00+02:00|talk|persuade|npc_1|dock|player_1|0|productive",
                roll_pool=3,
                difficulty=6,
                individual_rolls=[8, 2, 7],
                successes=2,
                is_success=True,
            )
            result = session.process_input("I persuade Jonas to help with the dock.")
        turn = session.get_last_action_resolution()

        self.assertDialogueFirstTalkOutput(result)
        self.assertIn("dock", result.output_text.lower())
        self.assertIn("paper trail", result.output_text.lower())
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertIsNotNone(turn.check)
        assert turn.check is not None
        self.assertEqual(turn.check.kind, DeterministicCheckKind.DIALOGUE_SOCIAL)
        self.assertTrue(turn.check.is_success)
        self.assertIsNotNone(turn.dialogue_adjudication)
        assert turn.dialogue_adjudication is not None
        self.assertTrue(turn.dialogue_adjudication.check_required)
        self.assertEqual(turn.dialogue_adjudication.reason_code, "persuade_check_required")
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.LEAD_PRESSURE)
        self.assertEqual(turn.adjudication.resolution_kind.name, "ROLL_GATED")
        self.assertIn("dialogue_social_check_success", turn.consequence_summary.applied_effects)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "lead_confirmed")
        self.assertIn("jonas_shared_dock_lead", session.get_world_state().story_flags)
        self.assertTrue(any("Rolled dialogue_social check" in entry.description for entry in session.get_world_state().event_log))
        self.assertTrue(any("Dialogue check success:" in entry.description for entry in session.get_world_state().event_log))
        self.assertEqual(session.get_conversation_focus_npc_id(), "npc_1")

    def test_failed_persuade_stays_guarded_and_does_not_advance_plot(self) -> None:
        session = GameSession()

        with patch("vampire_storyteller.game_session.resolve_deterministic_check") as mock_resolve:
            mock_resolve.return_value = DeterministicCheckResolution(
                kind=DeterministicCheckKind.DIALOGUE_SOCIAL,
                seed="2026-04-09T22:00:00+02:00|talk|persuade|npc_1|dock|player_1|0|productive",
                roll_pool=3,
                difficulty=6,
                individual_rolls=[2, 3, 4],
                successes=0,
                is_success=False,
            )
            result = session.process_input("I persuade Jonas to help with the dock.")
        turn = session.get_last_action_resolution()

        self.assertDialogueFirstTalkOutput(result)
        self.assertIn("not getting more", result.output_text.lower())
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertIsNotNone(turn.check)
        assert turn.check is not None
        self.assertFalse(turn.check.is_success)
        self.assertIsNotNone(turn.dialogue_adjudication)
        assert turn.dialogue_adjudication is not None
        self.assertTrue(turn.dialogue_adjudication.check_required)
        self.assertEqual(turn.dialogue_adjudication.reason_code, "persuade_check_required")
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.LEAD_PRESSURE)
        self.assertIn("dialogue_social_check_failure", turn.consequence_summary.applied_effects)
        self.assertTrue(any("Rolled dialogue_social check" in entry.description for entry in session.get_world_state().event_log))
        self.assertTrue(any("Dialogue check failed:" in entry.description for entry in session.get_world_state().event_log))
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")
        self.assertEqual(session.get_world_state().story_flags, [])
        self.assertEqual(session.get_conversation_stance(), ConversationStance.GUARDED)

    def test_jonas_dock_question_still_uses_productive_lead_path(self) -> None:
        session = GameSession()

        result = session.process_input("Jonas, what happened at the dock?")
        turn = session.get_last_action_resolution()

        self.assertIn("dock", result.output_text.lower())
        self.assertIn("paper trail", result.output_text.lower())
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertIsNotNone(turn.dialogue_adjudication)
        assert turn.dialogue_adjudication is not None
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.LEAD_TOPIC)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")

    def test_jonas_sex_request_does_not_reuse_dock_lead_or_advance_plot(self) -> None:
        session = GameSession()

        result = session.process_input("Jonas let us have sex")
        turn = session.get_last_action_resolution()

        self.assertIn("Keep this professional", result.output_text)
        self.assertNotIn("dock is the only place worth checking", result.output_text)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")
        self.assertEqual(session.get_world_state().story_flags, [])
        self.assertEqual(session.get_world_state().npcs["npc_1"].trust_level, 0)
        self.assertEqual(session.get_conversation_stance(), ConversationStance.GUARDED)
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertIsNotNone(turn.dialogue_adjudication)
        assert turn.dialogue_adjudication is not None
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.PROVOCATIVE_OR_INAPPROPRIATE)

    def test_jonas_blood_request_does_not_reuse_dock_lead_or_advance_plot(self) -> None:
        session = GameSession()

        result = session.process_input("Jonas I need blood")
        turn = session.get_last_action_resolution()

        self.assertIn("Ask someone else", result.output_text)
        self.assertNotIn("dock is the only place worth checking", result.output_text)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")
        self.assertEqual(session.get_world_state().story_flags, [])
        self.assertEqual(session.get_world_state().npcs["npc_1"].trust_level, 0)
        self.assertEqual(session.get_conversation_stance(), ConversationStance.NEUTRAL)
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertIsNotNone(turn.dialogue_adjudication)
        assert turn.dialogue_adjudication is not None
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.OFF_TOPIC_REQUEST)

    def test_jonas_travel_proposal_uses_distinct_logistics_response_without_plot_progress(self) -> None:
        session = GameSession()

        result = session.process_input("Jonas do you want to come with me to the docks?")
        turn = session.get_last_action_resolution()

        self.assertTrue(result.output_text.strip())
        self.assertNotIn("coming with you", result.output_text.lower())
        self.assertNotIn("stay nearby", result.output_text.lower())
        self.assertNotIn("visible accomplice", result.output_text.lower())
        self.assertNoUnsupportedLogisticsPromise(result.output_text)
        self.assertNotIn("dock is the only place worth checking", result.output_text)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")
        self.assertEqual(session.get_world_state().story_flags, [])
        self.assertEqual(session.get_world_state().npcs["npc_1"].trust_level, 0)
        self.assertEqual(session.get_conversation_stance(), ConversationStance.NEUTRAL)
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertIsNotNone(turn.dialogue_adjudication)
        assert turn.dialogue_adjudication is not None
        self.assertNotEqual(turn.social_outcome.logistics_commitment, LogisticsCommitment.NONE)
        self.assertIsNotNone(turn.social_outcome)
        assert turn.social_outcome is not None
        self.assertIn(
            turn.social_outcome.logistics_commitment,
            {
                LogisticsCommitment.DECLINE_JOIN,
                LogisticsCommitment.INDIRECT_SUPPORT,
            },
        )

    def test_logistics_contradiction_follow_up_stays_dialogue_first(self) -> None:
        session = GameSession()

        session.process_input("Jonas do you want to come with me to the docks?")
        result = session.process_input("How will you watch over me if you are not there at the docks with me.")
        turn = session.get_last_action_resolution()

        self.assertDialogueFirstTalkOutput(result)
        self.assertTrue(result.output_text.strip())
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertEqual(turn.canonical_action_text, "talk npc_1")
        self.assertIsNotNone(turn.dialogue_adjudication)
        self.assertIsNotNone(turn.social_outcome)
        assert turn.social_outcome is not None
        self.assertNotEqual(turn.social_outcome.logistics_commitment, LogisticsCommitment.NONE)
        self.assertNotEqual(turn.social_outcome.logistics_commitment, LogisticsCommitment.HIDDEN_SUPPORT)
        self.assertNoUnsupportedLogisticsPromise(result.output_text)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")
        self.assertEqual(session.get_world_state().story_flags, [])

    def test_recent_logistics_failure_sequence_never_promises_hidden_support(self) -> None:
        session = GameSession()

        lead_result = session.process_input("Jonas, what happened at the dock?")
        self.assertTrue(lead_result.output_text.strip())

        logistics_inputs = (
            "Come with me to the docks and back me up.",
            "Promise me.",
            "How will you watch over me if you are not there at the docks with me.",
        )

        for raw_input in logistics_inputs:
            result = session.process_input(raw_input)
            turn = session.get_last_action_resolution()

            self.assertDialogueFirstTalkOutput(result)
            self.assertNoUnsupportedLogisticsPromise(result.output_text)
            self.assertIsNotNone(turn)
            assert turn is not None
            self.assertEqual(turn.canonical_action_text, "talk npc_1")
            self.assertIsNone(turn.check)
            self.assertIsNotNone(turn.dialogue_adjudication)
            self.assertIsNotNone(turn.social_outcome)
            assert turn.social_outcome is not None
            self.assertNotEqual(turn.social_outcome.logistics_commitment, LogisticsCommitment.NONE)
            self.assertNotEqual(turn.social_outcome.logistics_commitment, LogisticsCommitment.HIDDEN_SUPPORT)
            self.assertIn(
                turn.social_outcome.logistics_commitment,
                {
                    LogisticsCommitment.ABSOLUTE_REFUSAL,
                    LogisticsCommitment.DECLINE_JOIN,
                    LogisticsCommitment.INDIRECT_SUPPORT,
                },
            )
            self.assertIsNotNone(turn.consequence_summary)
            self.assertIsInstance(session.get_world_state().event_log, list)
            self.assertIn(session.get_world_state().plots["plot_1"].stage, {"hook", "lead_confirmed"})

    def test_jonas_tell_me_more_after_productive_success_stays_coherent(self) -> None:
        session = GameSession()

        first_result = session.process_input("talk npc_1")
        second_result = session.process_input("talk npc_1")
        follow_up_result = session.process_input("Jonas, please tell me more")
        turn = session.get_last_action_resolution()

        self.assertIn("dock", first_result.output_text.lower())
        self.assertIn("paper trail", second_result.output_text.lower())
        self.assertTrue(follow_up_result.output_text.strip())
        self.assertNotIn("go on", follow_up_result.output_text.lower())
        self.assertNotIn("i'm listening", follow_up_result.output_text.lower())
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertIsNotNone(turn.dialogue_adjudication)
        assert turn.dialogue_adjudication is not None
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.LEAD_TOPIC)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "lead_confirmed")
        self.assertIn("trail starts", follow_up_result.output_text.lower())

    def test_guarded_blood_request_still_uses_off_topic_refusal(self) -> None:
        session = GameSession()

        session.process_input("I don't believe you.")
        result = session.process_input("Jonas I need blood")
        turn = session.get_last_action_resolution()

        self.assertIn("Ask someone else", result.output_text)
        self.assertNotIn("stays guarded and keeps the conversation tight", result.output_text)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")
        self.assertEqual(session.get_world_state().story_flags, [])
        self.assertEqual(session.get_conversation_stance(), ConversationStance.NEUTRAL)
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertIsNotNone(turn.dialogue_adjudication)
        assert turn.dialogue_adjudication is not None
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.OFF_TOPIC_REQUEST)

    def test_guarded_travel_request_still_uses_logistics_response(self) -> None:
        session = GameSession()

        session.process_input("I don't believe you.")
        result = session.process_input("Jonas do you want to come with me to the docks?")
        turn = session.get_last_action_resolution()

        self.assertTrue(result.output_text.strip())
        self.assertNotIn("coming with you", result.output_text.lower())
        self.assertNotIn("stay nearby", result.output_text.lower())
        self.assertNoUnsupportedLogisticsPromise(result.output_text)
        self.assertNotIn("stays guarded and keeps the conversation tight", result.output_text)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")
        self.assertEqual(session.get_world_state().story_flags, [])
        self.assertEqual(session.get_conversation_stance(), ConversationStance.NEUTRAL)
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertIsNotNone(turn.dialogue_adjudication)
        assert turn.dialogue_adjudication is not None
        self.assertNotEqual(turn.social_outcome.logistics_commitment, LogisticsCommitment.NONE)
        self.assertIsNotNone(turn.social_outcome)
        assert turn.social_outcome is not None
        self.assertIn(
            turn.social_outcome.logistics_commitment,
            {
                LogisticsCommitment.ABSOLUTE_REFUSAL,
                LogisticsCommitment.DECLINE_JOIN,
                LogisticsCommitment.INDIRECT_SUPPORT,
            },
        )

    def test_guarded_provocative_line_keeps_its_specific_guarded_refusal(self) -> None:
        session = GameSession()

        session.process_input("I don't believe you.")
        result = session.process_input("Jonas let us have sex")
        turn = session.get_last_action_resolution()

        self.assertIn("Keep this professional", result.output_text)
        self.assertNotIn("stays guarded and keeps the conversation tight", result.output_text)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")
        self.assertEqual(session.get_world_state().story_flags, [])
        self.assertEqual(session.get_conversation_stance(), ConversationStance.GUARDED)
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertIsNotNone(turn.dialogue_adjudication)
        assert turn.dialogue_adjudication is not None
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.PROVOCATIVE_OR_INAPPROPRIATE)

    def test_move_clears_conversation_focus(self) -> None:
        session = GameSession()

        session.process_input("talk npc_1")
        session.process_input("move loc_church")

        self.assertIsNone(session.get_conversation_focus_npc_id())
        self.assertEqual(session.get_conversation_stance(), ConversationStance.NEUTRAL)
        self.assertIsNone(session.get_conversation_subtopic())
        result = session.process_input("Why?")

        self.assertIn("Talk is blocked", result.output_text)
        self.assertIn("not present at Saint Judith's Church", result.output_text)

    def test_move_clears_missing_ledger_subtopic(self) -> None:
        session = GameSession()

        session.process_input("Jonas, what happened at the dock?")
        session.process_input("move loc_church")

        self.assertIsNone(session.get_conversation_focus_npc_id())
        self.assertIsNone(session.get_conversation_subtopic())

    def test_explicit_new_topic_overrides_missing_ledger_subtopic(self) -> None:
        session = GameSession()

        session.process_input("Jonas, what happened at the dock?")
        result = session.process_input("Jonas, do you have a spare car?")
        interpreted = session.get_last_interpreted_input()
        turn = session.get_last_action_resolution()

        self.assertTrue(
            any(
                phrase in result.output_text.lower()
                for phrase in ("not driving you", "indirectly", "absolutely not", "not in person")
            )
        )
        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertNotEqual(turn.social_outcome.logistics_commitment, LogisticsCommitment.NONE)
        self.assertEqual(session.get_conversation_subtopic(), DialogueSubtopic.TRANSPORT_OR_VEHICLE_SUPPORT)

    def test_follow_up_without_focus_returns_deterministic_feedback(self) -> None:
        session = GameSession()

        result = session.process_input("Go on.")

        self.assertEqual(result.output_text, "There is no active conversation to continue.")
        self.assertFalse(result.render_scene)
        self.assertIsNone(session.get_conversation_focus_npc_id())

    def test_question_without_focus_returns_deterministic_feedback(self) -> None:
        session = GameSession()

        result = session.process_input("Why?")

        self.assertEqual(result.output_text, "There is no active conversation to continue.")
        self.assertFalse(result.render_scene)

    def test_follow_up_phrase_without_focus_returns_deterministic_feedback(self) -> None:
        session = GameSession()

        result = session.process_input("What do you mean?")

        self.assertEqual(result.output_text, "There is no active conversation to continue.")
        self.assertFalse(result.render_scene)

    def test_load_clears_conversation_focus_and_stance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir) / "save.json"
            session = GameSession(save_path=save_path)

            session.process_input("talk npc_1")
            session.process_input("load")

            self.assertIsNone(session.get_conversation_focus_npc_id())
            self.assertEqual(session.get_conversation_stance(), ConversationStance.NEUTRAL)

    def test_follow_up_after_load_returns_stale_focus_feedback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir) / "save.json"
            session = GameSession(save_path=save_path)

            session.process_input("talk npc_1")
            session.process_input("save")
            session.process_input("load")
            result = session.process_input("Why?")

            self.assertIn("current conversation was reset when the save was loaded", result.output_text)
            self.assertFalse(result.render_scene)

    def test_explicit_other_npc_replaces_focus_when_available(self) -> None:
        session = GameSession()

        session.process_input("talk npc_1")
        session.process_input("move loc_church")
        result = session.process_input("Sister Eliza, good evening.")
        interpreted = session.get_last_interpreted_input()

        self.assertEqual(result.output_text, "Evening.")
        self.assertIsNotNone(result.dialogue_presentation)
        assert result.dialogue_presentation is not None
        self.assertEqual(result.dialogue_presentation.npc_display_name, "Sister Eliza")
        self.assertEqual(interpreted.target_reference, "npc_2")
        self.assertEqual(session.get_conversation_focus_npc_id(), "npc_2")

    def test_explicit_retarget_to_present_npc_after_focus_reset(self) -> None:
        session = GameSession()

        session.process_input("talk npc_1")
        session.process_input("move loc_church")
        result = session.process_input("Sister Eliza, we need to speak.")
        interpreted = session.get_last_interpreted_input()

        self.assertTrue(result.output_text.strip())
        self.assertIsNotNone(result.dialogue_presentation)
        assert result.dialogue_presentation is not None
        self.assertEqual(result.dialogue_presentation.npc_display_name, "Sister Eliza")
        self.assertEqual(interpreted.target_reference, "npc_2")
        self.assertEqual(session.get_conversation_focus_npc_id(), "npc_2")

    def test_natural_dialogue_to_absent_npc_returns_grounded_feedback(self) -> None:
        session = GameSession()

        result = session.process_input("Sister Eliza, we need to speak.")

        self.assertIn("Talk is blocked", result.output_text)
        self.assertIn("not present at Blackthorn Cafe", result.output_text)
        self.assertFalse(result.render_scene)

    def test_failed_explicit_retarget_clears_previous_focus_cleanly(self) -> None:
        session = GameSession()

        session.process_input("talk npc_1")
        result = session.process_input("talk npc_2")

        self.assertIn("Talk is blocked", result.output_text)
        self.assertIsNone(session.get_conversation_focus_npc_id())
        self.assertEqual(session.get_conversation_stance(), ConversationStance.NEUTRAL)

    def test_talk_can_shift_response_after_trust_improves(self) -> None:
        session = GameSession()

        first_result = session.process_input("talk npc_1")
        second_result = session.process_input("talk npc_1")

        self.assertIn("dock", first_result.output_text.lower())
        self.assertIn("paper trail", second_result.output_text.lower())
        self.assertIn("paper trail", second_result.output_text.lower())
        self.assertEqual(session.get_world_state().npcs["npc_1"].trust_level, 1)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "lead_confirmed")
        self.assertEqual(session.get_world_state().story_flags, ["jonas_shared_dock_lead"])

    def test_talk_one_shot_trust_hooks_do_not_stack_indefinitely(self) -> None:
        session = GameSession()

        session.process_input("talk npc_1")
        session.process_input("talk npc_1")
        session.process_input("talk npc_1")

        self.assertEqual(session.get_world_state().npcs["npc_1"].trust_level, 1)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "lead_confirmed")
        self.assertEqual(session.get_world_state().story_flags, ["jonas_shared_dock_lead"])

    def test_talk_to_absent_npc_returns_explicit_feedback(self) -> None:
        session = GameSession()

        result = session.process_input("talk npc_2")

        self.assertIn("Talk is blocked", result.output_text)
        self.assertIn("Sister Eliza", result.output_text)
        self.assertFalse(result.render_scene)

    def test_canonical_talk_without_metadata_still_works(self) -> None:
        session = GameSession()

        result = session.process_input("talk npc_1")

        self.assertTrue(result.output_text.strip())
        self.assertFalse(result.render_scene)

    def test_talk_uses_blocked_feedback_when_no_hook_matches_state(self) -> None:
        session = GameSession()

        session.process_input("move loc_church")
        session.process_input("wait 60")
        session.process_input("move loc_dock")
        session.process_input("investigate")
        result = session.process_input("talk npc_1")

        self.assertIn("Talk is blocked", result.output_text)
        self.assertIn("said what he will say", result.output_text)
        self.assertFalse(result.render_scene)
        self.assertIn("trust: 1", session.get_startup_text())

    def test_successful_investigate_updates_relevant_trust(self) -> None:
        session = GameSession()

        session.process_input("move loc_church")
        session.process_input("wait 60")
        session.process_input("move loc_dock")
        result = session.process_input("investigate")
        turn = session.get_last_action_resolution()

        self.assertTrue(result.render_scene)
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertIsNotNone(turn.check)
        assert turn.check is not None
        self.assertEqual(turn.check.kind, DeterministicCheckKind.INVESTIGATION)
        self.assertIsNotNone(turn.adjudication.check_spec)
        assert turn.adjudication.check_spec is not None
        self.assertEqual(turn.adjudication.check_spec.kind, DeterministicCheckKind.INVESTIGATION)
        self.assertIn("investigate_resolution_success", turn.consequence_summary.applied_effects)
        self.assertIn("plot_resolution_updated", turn.consequence_summary.applied_effects)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "resolved")
        self.assertIn("Plot 'Missing Ledger' resolved at North Dockside.", result.output_text)
        self.assertIn("Learned: The ledger's path points back to a hidden broker operating through the dock.", result.output_text)
        self.assertIn("Closing beat: Mara leaves North Dockside with the ledger matter settled.", result.output_text)
        self.assertEqual(session.get_world_state().npcs["npc_1"].trust_level, 1)
        self.assertEqual(session.get_world_state().npcs["npc_2"].trust_level, 2)
        self.assertEqual(session.get_world_state().story_flags, [])

    def test_save_load_restores_trust_reflected_in_scene_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir) / "save.json"
            session = GameSession(save_path=save_path)

            session.process_input("talk npc_1")
            session.process_input("save")

            reloaded_session = GameSession(save_path=save_path)
            load_result = reloaded_session.process_input("load")

            self.assertEqual(reloaded_session.get_world_state().npcs["npc_1"].trust_level, 1)
            self.assertIn("trust: 1", reloaded_session.get_startup_text())
            self.assertNotIn("Closing beat:", load_result.output_text)

    def test_injected_scene_provider_is_used_for_startup_and_mutations(self) -> None:
        provider = RecordingSceneProvider()
        session = GameSession(scene_provider=provider)

        startup_text = session.get_startup_text()
        look_result = session.process_input("look")
        move_result = session.process_input("move loc_church")

        self.assertEqual(startup_text, "rendered:2026-04-09T22:00:00+02:00")
        self.assertEqual(look_result.output_text, "rendered:2026-04-09T22:00:00+02:00")
        self.assertEqual(move_result.output_text, "rendered:2026-04-09T22:08:00+02:00")
        self.assertEqual(
            provider.rendered_world_times[:3],
            ["2026-04-09T22:00:00+02:00", "2026-04-09T22:00:00+02:00", "2026-04-09T22:08:00+02:00"],
        )

    def test_injected_scene_provider_is_used_after_wait_when_npcs_move(self) -> None:
        provider = RecordingSceneProvider()
        session = GameSession(scene_provider=provider)

        result = session.process_input("wait 60")

        self.assertEqual(result.output_text, "rendered:2026-04-09T23:00:00+02:00")
        self.assertEqual(provider.rendered_world_times[-1], "2026-04-09T23:00:00+02:00")
        self.assertEqual(session.get_world_state().npcs["npc_1"].location_id, "loc_dock")

    def test_help_status_and_quit_bypass_scene_provider(self) -> None:
        provider = RecordingSceneProvider()
        session = GameSession(scene_provider=provider)

        help_result = session.process_input("help")
        status_result = session.process_input("status")
        quit_result = session.process_input("quit")

        self.assertEqual(
            help_result.output_text.strip(),
            "look\nstatus\nhelp\nmove <destination_id>\nwait <minutes>\ntalk <npc_id>\ninvestigate\nsave\nload\nquit",
        )
        self.assertIn("Player:", status_result.output_text)
        self.assertTrue(quit_result.should_quit)
        self.assertEqual(provider.rendered_world_times, [])


if __name__ == "__main__":
    unittest.main()
