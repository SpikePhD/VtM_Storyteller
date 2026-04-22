from __future__ import annotations

import unittest

from vampire_storyteller.action_resolution import NormalizationSource
from vampire_storyteller.command_models import DialogueAct, DialogueMove
from vampire_storyteller.dialogue_intent_adapter import DialogueIntentContext, DialogueIntentProposal
from vampire_storyteller.game_session import GameSession
from vampire_storyteller.input_interpreter import InputInterpreter
from vampire_storyteller.models import NPC
from vampire_storyteller.dialogue_subtopic import DialogueSubtopic
from vampire_storyteller.sample_world import build_sample_world


class InputInterpreterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world_state = build_sample_world()
        self.interpreter = InputInterpreter()

    class RecordingDialogueIntentAdapter:
        def __init__(self) -> None:
            self.contexts: list[DialogueIntentContext] = []
            self._classifier = InputInterpreter()

        def propose_dialogue_intent(self, context: DialogueIntentContext) -> DialogueIntentProposal:
            self.contexts.append(context)
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
            return DialogueIntentProposal(
                dialogue_act=dialogue_act.value,
                dialogue_move=dialogue_move.value,
                target_npc_text=context.conversation_focus_npc_name or "Jonas Reed",
                topic=self._infer_topic(normalized_text, dialogue_act),
                tone=self._infer_tone(dialogue_act, dialogue_move, normalized_text),
            )

        def _infer_topic(self, normalized_text: str, dialogue_act: DialogueAct) -> str:
            if any(
                phrase in normalized_text
                for phrase in (
                    "ledger",
                    "paper trail",
                    "dock",
                    "docks",
                    "church records",
                    "records",
                    "trail",
                )
            ):
                return "missing_ledger"
            if any(
                phrase in normalized_text
                for phrase in (
                    "back me up",
                    "backup",
                    "back up",
                    "stay nearby",
                    "wait nearby",
                    "stay close",
                    "stay in the car",
                    "come along",
                )
            ):
                return "backup"
            if any(
                phrase in normalized_text
                for phrase in (
                    "drive",
                    "ride",
                    "lift",
                    "vehicle",
                    "car",
                    "drop me off",
                    "transport",
                )
            ):
                return "transport"
            if any(phrase in normalized_text for phrase in ("blood", "feed", "vampire")):
                return "blood"
            if dialogue_act in {DialogueAct.ASK, DialogueAct.PERSUADE, DialogueAct.ACCUSE, DialogueAct.THREATEN}:
                return "lead_topic"
            return "conversation"

        def _infer_tone(self, dialogue_act: DialogueAct, dialogue_move: DialogueMove, normalized_text: str) -> str:
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

    def _interpret_with_active_dialogue_adapter(self, raw_input: str, **kwargs):
        adapter = self.RecordingDialogueIntentAdapter()
        result = self.interpreter.interpret(raw_input, self.world_state, dialogue_intent_adapter=adapter, **kwargs)
        return result, adapter

    class UnusableDialogueIntentAdapter:
        def propose_dialogue_intent(self, context: DialogueIntentContext) -> DialogueIntentProposal | None:
            return None

    def test_freeform_careful_look_maps_to_look(self) -> None:
        result = self.interpreter.interpret("I take a careful look around.", self.world_state)

        self.assertFalse(result.fallback_to_parser)
        self.assertEqual(result.normalized_intent, "look")
        self.assertEqual(result.canonical_command, "look")
        self.assertIsNone(result.target_reference)

    def test_freeform_ambiguous_observation_prefers_look(self) -> None:
        result = self.interpreter.interpret(
            "I feel disturbed by the environment. I take a look around to see if something is wrong.",
            self.world_state,
        )

        self.assertFalse(result.fallback_to_parser)
        self.assertEqual(result.normalized_intent, "look")
        self.assertEqual(result.canonical_command, "look")
        self.assertIsNone(result.target_reference)

    def test_freeform_search_maps_to_investigate(self) -> None:
        result = self.interpreter.interpret("I search the area for clues.", self.world_state)

        self.assertFalse(result.fallback_to_parser)
        self.assertEqual(result.normalized_intent, "investigate")
        self.assertEqual(result.canonical_command, "investigate")

    def test_freeform_careful_inspection_maps_to_investigate(self) -> None:
        result = self.interpreter.interpret("I inspect the scene carefully for evidence.", self.world_state)

        self.assertFalse(result.fallback_to_parser)
        self.assertEqual(result.normalized_intent, "investigate")
        self.assertEqual(result.canonical_command, "investigate")

    def test_freeform_movement_maps_to_move(self) -> None:
        result = self.interpreter.interpret("I head to the church.", self.world_state)

        self.assertFalse(result.fallback_to_parser)
        self.assertEqual(result.normalized_intent, "move")
        self.assertEqual(result.target_reference, "loc_church")
        self.assertEqual(result.canonical_command, "move loc_church")

    def test_freeform_wait_maps_to_wait(self) -> None:
        result = self.interpreter.interpret("Wait for 30 minutes.", self.world_state)

        self.assertFalse(result.fallback_to_parser)
        self.assertEqual(result.normalized_intent, "wait")
        self.assertEqual(result.canonical_command, "wait 30")
        self.assertEqual(result.target_text, "30")

    def test_freeform_greeting_maps_to_talk_with_greet_act(self) -> None:
        result = self.interpreter.interpret("Jonas, good evening.", self.world_state)

        self.assertFalse(result.fallback_to_parser)
        self.assertEqual(result.normalized_intent, "talk")
        self.assertEqual(result.target_reference, "npc_1")
        self.assertEqual(result.canonical_command, "talk npc_1")
        self.assertIsNotNone(result.dialogue_metadata)
        self.assertEqual(result.dialogue_metadata.utterance_text, "Jonas, good evening.")
        self.assertEqual(result.dialogue_metadata.speech_text, "good evening.")
        self.assertEqual(result.dialogue_metadata.dialogue_act, DialogueAct.GREET)

    def test_freeform_question_maps_to_ask_act(self) -> None:
        result = self.interpreter.interpret("Jonas, what happened here?", self.world_state)

        self.assertFalse(result.fallback_to_parser)
        self.assertEqual(result.target_reference, "npc_1")
        self.assertEqual(result.dialogue_metadata.dialogue_act, DialogueAct.ASK)

    def test_freeform_accusation_maps_to_accuse_act(self) -> None:
        result = self.interpreter.interpret("Jonas, you're hiding something.", self.world_state)

        self.assertFalse(result.fallback_to_parser)
        self.assertEqual(result.target_reference, "npc_1")
        self.assertEqual(result.dialogue_metadata.dialogue_act, DialogueAct.ACCUSE)

    def test_freeform_speak_to_maps_to_talk(self) -> None:
        result = self.interpreter.interpret("I speak to Jonas.", self.world_state)

        self.assertFalse(result.fallback_to_parser)
        self.assertEqual(result.target_reference, "npc_1")
        self.assertEqual(result.canonical_command, "talk npc_1")

    def test_freeform_direct_address_maps_to_present_npc(self) -> None:
        result = self.interpreter.interpret("Jonas, we need to speak.", self.world_state)

        self.assertFalse(result.fallback_to_parser)
        self.assertEqual(result.target_reference, "npc_1")
        self.assertEqual(result.canonical_command, "talk npc_1")

    def test_freeform_talk_to_maps_to_talk(self) -> None:
        result = self.interpreter.interpret("I talk to Jonas.", self.world_state)

        self.assertFalse(result.fallback_to_parser)
        self.assertEqual(result.target_reference, "npc_1")
        self.assertEqual(result.canonical_command, "talk npc_1")

    def test_freeform_ask_form_maps_to_talk(self) -> None:
        result = self.interpreter.interpret("I ask Jonas what happened here.", self.world_state)

        self.assertFalse(result.fallback_to_parser)
        self.assertEqual(result.target_reference, "npc_1")
        self.assertEqual(result.dialogue_metadata.dialogue_act, DialogueAct.ASK)

    def test_freeform_accuse_form_maps_to_talk(self) -> None:
        result = self.interpreter.interpret("I accuse Jonas of hiding something.", self.world_state)

        self.assertFalse(result.fallback_to_parser)
        self.assertEqual(result.target_reference, "npc_1")
        self.assertEqual(result.dialogue_metadata.dialogue_act, DialogueAct.ACCUSE)

    def test_freeform_targeted_line_can_fall_back_to_unknown_act(self) -> None:
        result = self.interpreter.interpret("Jonas, the city is cold.", self.world_state)

        self.assertFalse(result.fallback_to_parser)
        self.assertEqual(result.target_reference, "npc_1")
        self.assertEqual(result.dialogue_metadata.dialogue_act, DialogueAct.UNKNOWN)
        self.assertEqual(result.dialogue_metadata.speech_text, "the city is cold.")

    def test_statement_style_acknowledgement_uses_react_move(self) -> None:
        result = self.interpreter.interpret("Jonas, just coming to say hi.", self.world_state)

        self.assertFalse(result.fallback_to_parser)
        self.assertEqual(result.target_reference, "npc_1")
        self.assertEqual(result.dialogue_metadata.dialogue_act, DialogueAct.GREET)
        self.assertEqual(result.dialogue_metadata.dialogue_move, DialogueMove.REACT)

    def test_statement_style_continuation_uses_continue_move(self) -> None:
        result = self.interpreter.interpret("Jonas, sure. Tell me.", self.world_state)

        self.assertFalse(result.fallback_to_parser)
        self.assertEqual(result.target_reference, "npc_1")
        self.assertEqual(result.dialogue_metadata.dialogue_act, DialogueAct.UNKNOWN)
        self.assertEqual(result.dialogue_metadata.dialogue_move, DialogueMove.CONTINUE)

    def test_statement_style_clarify_uses_clarify_move(self) -> None:
        result = self.interpreter.interpret("Jonas, you just did.", self.world_state)

        self.assertFalse(result.fallback_to_parser)
        self.assertEqual(result.target_reference, "npc_1")
        self.assertEqual(result.dialogue_metadata.dialogue_act, DialogueAct.UNKNOWN)
        self.assertEqual(result.dialogue_metadata.dialogue_move, DialogueMove.CLARIFY)

    def test_statement_style_banter_uses_banter_move(self) -> None:
        result = self.interpreter.interpret("Jonas, there you are! anyhow, I know you have information for me.", self.world_state)

        self.assertFalse(result.fallback_to_parser)
        self.assertEqual(result.target_reference, "npc_1")
        self.assertEqual(result.dialogue_metadata.dialogue_move, DialogueMove.BANTER)

    def test_meta_question_uses_clarify_move(self) -> None:
        result = self.interpreter.interpret("Jonas, are you repeating what I am saying?", self.world_state)

        self.assertFalse(result.fallback_to_parser)
        self.assertEqual(result.target_reference, "npc_1")
        self.assertEqual(result.dialogue_metadata.dialogue_act, DialogueAct.ASK)
        self.assertEqual(result.dialogue_metadata.dialogue_move, DialogueMove.CLARIFY)

    def test_unrecognized_input_falls_back_to_parser(self) -> None:
        result = self.interpreter.interpret("sing a song", self.world_state)

        self.assertTrue(result.fallback_to_parser)
        self.assertIsNone(result.canonical_command)
        self.assertEqual(result.confidence, 0.0)

    def test_freeform_unknown_dialogue_target_returns_grounded_failure(self) -> None:
        result = self.interpreter.interpret("Elena, we need to speak.", self.world_state)

        self.assertFalse(result.fallback_to_parser)
        self.assertIsNone(result.canonical_command)
        self.assertIsNotNone(result.failure_reason)
        self.assertIn("could not identify", result.failure_reason or "")

    def test_freeform_ambiguous_dialogue_target_returns_grounded_failure(self) -> None:
        world = build_sample_world()
        world.npcs["npc_3"] = NPC(
            id="npc_3",
            name="Elena Vale",
            role="Observer",
            location_id="loc_cafe",
            attitude_to_player="wary",
            trust_level=0,
            consumed_dialogue_hooks=[],
            goals=[],
            investigation_hint="",
            schedule={},
            traits={},
        )
        world.npcs["npc_4"] = NPC(
            id="npc_4",
            name="Elena Sera",
            role="Observer",
            location_id="loc_cafe",
            attitude_to_player="wary",
            trust_level=0,
            consumed_dialogue_hooks=[],
            goals=[],
            investigation_hint="",
            schedule={},
            traits={},
        )

        result = self.interpreter.interpret("Elena, we need to speak.", world)

        self.assertFalse(result.fallback_to_parser)
        self.assertIsNone(result.canonical_command)
        self.assertIsNotNone(result.failure_reason)
        self.assertIn("ambiguous", result.failure_reason or "")

    def test_game_session_accepts_freeform_input(self) -> None:
        session = GameSession()

        result = session.process_input("I head to the church.")
        normalized = session.get_last_normalized_action()

        self.assertTrue(result.render_scene)
        self.assertEqual(session.get_world_state().player.location_id, "loc_church")
        self.assertIsNotNone(normalized)
        assert normalized is not None
        self.assertEqual(normalized.source, NormalizationSource.INTERPRETED)
        self.assertEqual(normalized.canonical_command_text, "move loc_church")

    def test_game_session_preserves_dialogue_metadata(self) -> None:
        session = GameSession()

        session.process_input("Jonas, I need you to trust me.")
        interpreted = session.get_last_interpreted_input()
        normalized = session.get_last_normalized_action()

        self.assertIsNotNone(interpreted)
        self.assertIsNotNone(interpreted.dialogue_metadata)
        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertEqual(interpreted.dialogue_metadata.dialogue_act, DialogueAct.PERSUADE)
        self.assertEqual(interpreted.dialogue_metadata.utterance_text, "Jonas, I need you to trust me.")
        self.assertIsNotNone(normalized)
        assert normalized is not None
        self.assertEqual(normalized.source, NormalizationSource.INTERPRETED)
        self.assertEqual(normalized.canonical_command_text, "talk npc_1")

    def test_follow_up_uses_conversation_focus(self) -> None:
        result, _adapter = self._interpret_with_active_dialogue_adapter("Why?", conversation_focus_npc_id="npc_1")

        self.assertFalse(result.fallback_to_parser)
        self.assertEqual(result.normalized_intent, "talk")
        self.assertEqual(result.target_reference, "npc_1")
        self.assertEqual(result.dialogue_metadata.dialogue_act, DialogueAct.ASK)

    def test_follow_up_what_do_you_mean_uses_conversation_focus(self) -> None:
        result, _adapter = self._interpret_with_active_dialogue_adapter("What do you mean?", conversation_focus_npc_id="npc_1")

        self.assertFalse(result.fallback_to_parser)
        self.assertEqual(result.normalized_intent, "talk")
        self.assertEqual(result.target_reference, "npc_1")
        self.assertEqual(result.dialogue_metadata.dialogue_act, DialogueAct.ASK)

    def test_follow_up_skeptical_line_uses_conversation_focus(self) -> None:
        result, _adapter = self._interpret_with_active_dialogue_adapter("I don't believe you.", conversation_focus_npc_id="npc_1")

        self.assertFalse(result.fallback_to_parser)
        self.assertEqual(result.normalized_intent, "talk")
        self.assertEqual(result.target_reference, "npc_1")
        self.assertEqual(result.dialogue_metadata.dialogue_act, DialogueAct.ACCUSE)

    def test_follow_up_that_sounds_wrong_uses_conversation_focus(self) -> None:
        result, _adapter = self._interpret_with_active_dialogue_adapter("That sounds wrong.", conversation_focus_npc_id="npc_1")

        self.assertFalse(result.fallback_to_parser)
        self.assertEqual(result.normalized_intent, "talk")
        self.assertEqual(result.target_reference, "npc_1")
        self.assertEqual(result.dialogue_metadata.dialogue_act, DialogueAct.ACCUSE)

    def test_pronoun_follow_up_reuses_valid_conversation_focus(self) -> None:
        result, _adapter = self._interpret_with_active_dialogue_adapter(
            "I turn back to her and continue.",
            conversation_focus_npc_id="npc_1",
        )

        self.assertFalse(result.fallback_to_parser)
        self.assertEqual(result.normalized_intent, "talk")
        self.assertEqual(result.target_reference, "npc_1")
        self.assertEqual(result.canonical_command, "talk npc_1")
        self.assertIsNotNone(result.dialogue_metadata)
        self.assertIn("continue", result.dialogue_metadata.utterance_text.lower())

    def test_backup_follow_up_uses_conversation_focus(self) -> None:
        result, _adapter = self._interpret_with_active_dialogue_adapter("I need you as a back up", conversation_focus_npc_id="npc_1")

        self.assertFalse(result.fallback_to_parser)
        self.assertEqual(result.normalized_intent, "talk")
        self.assertEqual(result.target_reference, "npc_1")
        self.assertEqual(result.canonical_command, "talk npc_1")

    def test_meta_conversation_follow_up_routes_through_dialogue_intent(self) -> None:
        adapter = self.RecordingDialogueIntentAdapter()
        result = self.interpreter.interpret(
            "Why are you so hostile?",
            self.world_state,
            conversation_focus_npc_id="npc_1",
            dialogue_intent_adapter=adapter,
        )

        self.assertFalse(result.fallback_to_parser)
        self.assertEqual(result.normalized_intent, "talk")
        self.assertEqual(result.target_reference, "npc_1")
        self.assertIsNotNone(result.dialogue_metadata)
        assert result.dialogue_metadata is not None
        self.assertEqual(result.dialogue_metadata.dialogue_act, DialogueAct.ASK)
        self.assertEqual(len(adapter.contexts), 1)

    def test_missing_ledger_follow_up_reuses_active_subtopic(self) -> None:
        result, _adapter = self._interpret_with_active_dialogue_adapter(
            "What about it",
            conversation_focus_npc_id="npc_1",
            conversation_subtopic=DialogueSubtopic.MISSING_LEDGER,
        )

        self.assertFalse(result.fallback_to_parser)
        self.assertEqual(result.normalized_intent, "talk")
        self.assertEqual(result.target_reference, "npc_1")
        self.assertEqual(result.canonical_command, "talk npc_1")
        self.assertIsNotNone(result.dialogue_metadata)
        assert result.dialogue_metadata is not None
        self.assertEqual(result.dialogue_metadata.dialogue_act, DialogueAct.ASK)

    def test_logistics_follow_up_with_acknowledgement_uses_conversation_focus(self) -> None:
        result, _adapter = self._interpret_with_active_dialogue_adapter(
            "Yes we are. But I need you to back me up",
            conversation_focus_npc_id="npc_1",
        )

        self.assertFalse(result.fallback_to_parser)
        self.assertEqual(result.normalized_intent, "talk")
        self.assertEqual(result.target_reference, "npc_1")
        self.assertEqual(result.canonical_command, "talk npc_1")

    def test_active_conversation_declarative_line_routes_through_dialogue_intent_by_default(self) -> None:
        adapter = self.RecordingDialogueIntentAdapter()
        result = self.interpreter.interpret(
            "Just coming to say hi to an old friend...",
            self.world_state,
            conversation_focus_npc_id="npc_1",
            dialogue_intent_adapter=adapter,
        )

        self.assertFalse(result.fallback_to_parser)
        self.assertEqual(result.normalized_intent, "talk")
        self.assertEqual(result.target_reference, "npc_1")
        self.assertIsNotNone(result.dialogue_metadata)
        assert result.dialogue_metadata is not None
        self.assertEqual(result.dialogue_metadata.dialogue_act, DialogueAct.GREET)
        self.assertEqual(len(adapter.contexts), 1)
        self.assertEqual(adapter.contexts[0].conversation_focus_npc_id, "npc_1")
        self.assertEqual(adapter.contexts[0].raw_input, "Just coming to say hi to an old friend...")

    def test_active_conversation_explicit_world_action_stays_on_existing_path(self) -> None:
        adapter = self.RecordingDialogueIntentAdapter()
        result = self.interpreter.interpret(
            "look around the church",
            self.world_state,
            conversation_focus_npc_id="npc_1",
            dialogue_intent_adapter=adapter,
        )

        self.assertFalse(result.fallback_to_parser)
        self.assertEqual(result.normalized_intent, "look")
        self.assertEqual(result.canonical_command, "look")
        self.assertEqual(adapter.contexts, [])

    def test_active_conversation_unusable_adapter_falls_back_to_local_dialogue_classification(self) -> None:
        adapter = self.UnusableDialogueIntentAdapter()
        result = self.interpreter.interpret(
            "But I need your help.",
            self.world_state,
            conversation_focus_npc_id="npc_1",
            dialogue_intent_adapter=adapter,
        )

        self.assertFalse(result.fallback_to_parser)
        self.assertEqual(result.normalized_intent, "talk")
        self.assertEqual(result.target_reference, "npc_1")
        self.assertEqual(result.canonical_command, "talk npc_1")
        self.assertIsNotNone(result.dialogue_metadata)
        assert result.dialogue_metadata is not None
        self.assertEqual(result.dialogue_metadata.dialogue_act, DialogueAct.PERSUADE)
        self.assertEqual(result.dialogue_metadata.dialogue_move, DialogueMove.CONTINUE)
        self.assertIsNone(result.failure_reason)

    def test_active_conversation_pressure_line_stays_in_dialogue_after_adapter_failure(self) -> None:
        adapter = self.UnusableDialogueIntentAdapter()
        result = self.interpreter.interpret(
            "Listen I don't have time for this. What do you know",
            self.world_state,
            conversation_focus_npc_id="npc_1",
            dialogue_intent_adapter=adapter,
        )

        self.assertFalse(result.fallback_to_parser)
        self.assertEqual(result.normalized_intent, "talk")
        self.assertEqual(result.target_reference, "npc_1")
        self.assertEqual(result.canonical_command, "talk npc_1")
        self.assertIsNotNone(result.dialogue_metadata)
        assert result.dialogue_metadata is not None
        self.assertIn(result.dialogue_metadata.dialogue_act, {DialogueAct.ASK, DialogueAct.UNKNOWN})
        self.assertEqual(result.dialogue_metadata.dialogue_move, DialogueMove.CONTINUE)
        self.assertIsNone(result.failure_reason)

    def test_missing_ledger_statement_follow_up_uses_active_conversation_focus(self) -> None:
        result, _adapter = self._interpret_with_active_dialogue_adapter(
            "I need you to tell me what you know about the missing ledger",
            conversation_focus_npc_id="npc_1",
        )

        self.assertFalse(result.fallback_to_parser)
        self.assertEqual(result.normalized_intent, "talk")
        self.assertEqual(result.target_reference, "npc_1")
        self.assertEqual(result.canonical_command, "talk npc_1")
        self.assertIsNotNone(result.dialogue_metadata)
        assert result.dialogue_metadata is not None
        self.assertEqual(result.dialogue_metadata.dialogue_act, DialogueAct.PERSUADE)

    def test_follow_up_against_stale_focus_returns_grounded_failure(self) -> None:
        result = self.interpreter.interpret(
            "Why?",
            self.world_state,
            stale_conversation_focus_npc_id="npc_1",
            stale_conversation_focus_reason="Talk is blocked: Jonas Reed is no longer present at Saint Judith's Church.",
        )

        self.assertFalse(result.fallback_to_parser)
        self.assertIsNone(result.canonical_command)
        self.assertIsNotNone(result.failure_reason)
        self.assertIn("no longer present", result.failure_reason or "")

    def test_follow_up_without_focus_falls_back(self) -> None:
        result = self.interpreter.interpret("Why?", self.world_state)

        self.assertFalse(result.fallback_to_parser)
        self.assertTrue(result.no_active_conversation)
        self.assertIsNone(result.canonical_command)

    def test_go_on_without_focus_returns_no_active_conversation_result(self) -> None:
        result = self.interpreter.interpret("Go on.", self.world_state)

        self.assertFalse(result.fallback_to_parser)
        self.assertTrue(result.no_active_conversation)
        self.assertEqual(result.match_reason, "follow-up dialogue was attempted without an active conversation focus")

    def test_skeptical_follow_up_without_focus_returns_no_active_conversation_result(self) -> None:
        result = self.interpreter.interpret("I don't believe you.", self.world_state)

        self.assertFalse(result.fallback_to_parser)
        self.assertTrue(result.no_active_conversation)
        self.assertIsNone(result.canonical_command)

    def test_backup_follow_up_without_focus_returns_no_active_conversation_result(self) -> None:
        result = self.interpreter.interpret("I need you as a back up", self.world_state)

        self.assertFalse(result.fallback_to_parser)
        self.assertTrue(result.no_active_conversation)
        self.assertIsNone(result.canonical_command)


if __name__ == "__main__":
    unittest.main()
