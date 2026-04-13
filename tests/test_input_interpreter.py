from __future__ import annotations

import unittest

from vampire_storyteller.command_models import DialogueAct
from vampire_storyteller.game_session import GameSession
from vampire_storyteller.input_interpreter import InputInterpreter
from vampire_storyteller.sample_world import build_sample_world


class InputInterpreterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world_state = build_sample_world()
        self.interpreter = InputInterpreter()

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

    def test_unrecognized_input_falls_back_to_parser(self) -> None:
        result = self.interpreter.interpret("sing a song", self.world_state)

        self.assertTrue(result.fallback_to_parser)
        self.assertIsNone(result.canonical_command)
        self.assertEqual(result.confidence, 0.0)

    def test_game_session_accepts_freeform_input(self) -> None:
        session = GameSession()

        result = session.process_input("I head to the church.")

        self.assertTrue(result.render_scene)
        self.assertEqual(session.get_world_state().player.location_id, "loc_church")

    def test_game_session_preserves_dialogue_metadata(self) -> None:
        session = GameSession()

        session.process_input("Jonas, I need you to trust me.")
        interpreted = session.get_last_interpreted_input()

        self.assertIsNotNone(interpreted)
        self.assertIsNotNone(interpreted.dialogue_metadata)
        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertEqual(interpreted.dialogue_metadata.dialogue_act, DialogueAct.PERSUADE)
        self.assertEqual(interpreted.dialogue_metadata.utterance_text, "Jonas, I need you to trust me.")

    def test_follow_up_uses_conversation_focus(self) -> None:
        result = self.interpreter.interpret("Why?", self.world_state, conversation_focus_npc_id="npc_1")

        self.assertFalse(result.fallback_to_parser)
        self.assertEqual(result.normalized_intent, "talk")
        self.assertEqual(result.target_reference, "npc_1")
        self.assertEqual(result.dialogue_metadata.dialogue_act, DialogueAct.ASK)

    def test_follow_up_what_do_you_mean_uses_conversation_focus(self) -> None:
        result = self.interpreter.interpret("What do you mean?", self.world_state, conversation_focus_npc_id="npc_1")

        self.assertFalse(result.fallback_to_parser)
        self.assertEqual(result.normalized_intent, "talk")
        self.assertEqual(result.target_reference, "npc_1")
        self.assertEqual(result.dialogue_metadata.dialogue_act, DialogueAct.ASK)

    def test_follow_up_skeptical_line_uses_conversation_focus(self) -> None:
        result = self.interpreter.interpret("I don't believe you.", self.world_state, conversation_focus_npc_id="npc_1")

        self.assertFalse(result.fallback_to_parser)
        self.assertEqual(result.normalized_intent, "talk")
        self.assertEqual(result.target_reference, "npc_1")
        self.assertEqual(result.dialogue_metadata.dialogue_act, DialogueAct.ACCUSE)

    def test_follow_up_that_sounds_wrong_uses_conversation_focus(self) -> None:
        result = self.interpreter.interpret("That sounds wrong.", self.world_state, conversation_focus_npc_id="npc_1")

        self.assertFalse(result.fallback_to_parser)
        self.assertEqual(result.normalized_intent, "talk")
        self.assertEqual(result.target_reference, "npc_1")
        self.assertEqual(result.dialogue_metadata.dialogue_act, DialogueAct.ACCUSE)

    def test_follow_up_without_focus_falls_back(self) -> None:
        result = self.interpreter.interpret("Why?", self.world_state)

        self.assertTrue(result.fallback_to_parser)
        self.assertIsNone(result.canonical_command)


if __name__ == "__main__":
    unittest.main()
