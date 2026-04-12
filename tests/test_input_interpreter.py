from __future__ import annotations

import unittest

from vampire_storyteller.game_session import GameSession
from vampire_storyteller.input_interpreter import InputInterpreter
from vampire_storyteller.sample_world import build_sample_world


class InputInterpreterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world_state = build_sample_world()
        self.interpreter = InputInterpreter()

    def test_freeform_observation_maps_to_investigate(self) -> None:
        result = self.interpreter.interpret(
            "I feel disturbed by the environment. I take a look around to see if something is wrong.",
            self.world_state,
        )

        self.assertFalse(result.fallback_to_parser)
        self.assertEqual(result.normalized_intent, "investigate")
        self.assertEqual(result.canonical_command, "investigate")
        self.assertIsNone(result.target_reference)

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

    def test_freeform_talk_maps_to_talk(self) -> None:
        result = self.interpreter.interpret("Jonas, tell me what happened here.", self.world_state)

        self.assertFalse(result.fallback_to_parser)
        self.assertEqual(result.normalized_intent, "talk")
        self.assertEqual(result.target_reference, "npc_1")
        self.assertEqual(result.canonical_command, "talk npc_1")

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


if __name__ == "__main__":
    unittest.main()
