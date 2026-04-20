from __future__ import annotations

import unittest
from unittest.mock import patch

from vampire_storyteller.config import AppConfig
from vampire_storyteller.cli import build_dialogue_renderer
from vampire_storyteller.dialogue_renderer import (
    DeterministicDialogueRenderer,
    build_dialogue_render_input,
)
from vampire_storyteller.dice_engine import DeterministicCheckKind, DeterministicCheckResolution
from vampire_storyteller.game_session import GameSession


class FailingDialogueRenderer:
    def render_dialogue(self, render_input) -> str:
        raise RuntimeError("dialogue renderer failed")


class DialogueRendererTests(unittest.TestCase):
    def test_productive_lead_reply_renders_from_structured_outcome(self) -> None:
        session = GameSession()

        result = session.process_input("Jonas, what happened at the dock?")

        self.assertIn("dock", result.output_text.lower())
        self.assertIn("jonas reed", result.output_text.lower())
        self.assertNotIn("Talk is guarded", result.output_text)

    def test_social_check_success_renders_from_structured_success_data(self) -> None:
        session = GameSession()

        with patch("vampire_storyteller.game_session.resolve_deterministic_check") as mock_resolve:
            mock_resolve.return_value = DeterministicCheckResolution(
                kind=DeterministicCheckKind.DIALOGUE_SOCIAL,
                seed="success-seed",
                roll_pool=3,
                difficulty=6,
                individual_rolls=[7, 8, 2],
                successes=2,
                is_success=True,
            )
            result = session.process_input("I persuade Jonas to help with the dock.")

        self.assertIn("waterline", result.output_text.lower())
        self.assertIn("broker", result.output_text.lower())
        self.assertNotIn("Dialogue check success", result.output_text)

    def test_social_check_failure_renders_from_structured_failure_data(self) -> None:
        session = GameSession()

        with patch("vampire_storyteller.game_session.resolve_deterministic_check") as mock_resolve:
            mock_resolve.return_value = DeterministicCheckResolution(
                kind=DeterministicCheckKind.DIALOGUE_SOCIAL,
                seed="failure-seed",
                roll_pool=3,
                difficulty=6,
                individual_rolls=[1, 3, 4],
                successes=0,
                is_success=False,
            )
            result = session.process_input("I persuade Jonas to help with the dock.")

        self.assertIn("guarded", result.output_text.lower())
        self.assertNotIn("Dialogue check failed", result.output_text)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")

    def test_provocative_refusal_renders_from_structured_domain_outcome(self) -> None:
        session = GameSession()

        result = session.process_input("Jonas let us have sex")

        self.assertIn("keep this professional", result.output_text.lower())
        self.assertNotIn("Talk is guarded", result.output_text)

    def test_travel_logistics_reply_renders_from_structured_domain_outcome(self) -> None:
        session = GameSession()

        result = session.process_input("Jonas do you want to come with me to the docks?")

        self.assertIn("if the dock matters, you go", result.output_text.lower())
        self.assertIn("noise", result.output_text.lower())

    def test_renderer_output_does_not_mutate_world_state(self) -> None:
        session = GameSession()
        session.process_input("Jonas, what happened at the dock?")
        turn = session.get_last_action_resolution()
        assert turn is not None
        assert turn.dialogue_adjudication is not None
        command = turn.normalized_action.command
        assert command is not None
        render_input = build_dialogue_render_input(
            session.get_world_state(),
            command,
            turn.dialogue_adjudication,
            turn.check,
            turn.consequence_summary,
        )
        renderer = DeterministicDialogueRenderer()
        before = (
            session.get_world_state().plots["plot_1"].stage,
            tuple(session.get_world_state().story_flags),
            session.get_world_state().npcs["npc_1"].trust_level,
        )

        output = renderer.render_dialogue(render_input)

        after = (
            session.get_world_state().plots["plot_1"].stage,
            tuple(session.get_world_state().story_flags),
            session.get_world_state().npcs["npc_1"].trust_level,
        )
        self.assertTrue(output.strip())
        self.assertEqual(before, after)

    def test_session_falls_back_to_deterministic_dialogue_renderer_when_renderer_fails(self) -> None:
        session = GameSession(dialogue_renderer=FailingDialogueRenderer())

        result = session.process_input("Jonas, what happened at the dock?")

        self.assertIn("dock", result.output_text.lower())
        self.assertIn("jonas reed", result.output_text.lower())

    def test_dialogue_renderer_helper_uses_deterministic_renderer_when_openai_not_selected(self) -> None:
        renderer, notice = build_dialogue_renderer(
            AppConfig(
                openai_api_key=None,
                openai_model="gpt-4.1-mini",
                use_openai_scene_provider=False,
                use_openai_dialogue_intent_adapter=False,
                use_openai_dialogue_renderer=False,
            )
        )

        self.assertIsInstance(renderer, DeterministicDialogueRenderer)
        self.assertIsNone(notice)

    def test_missing_api_key_for_openai_dialogue_renderer_falls_back_safely(self) -> None:
        renderer, notice = build_dialogue_renderer(
            AppConfig(
                openai_api_key=None,
                openai_model="gpt-4.1-mini",
                use_openai_scene_provider=False,
                use_openai_dialogue_intent_adapter=False,
                use_openai_dialogue_renderer=True,
            )
        )

        self.assertIsInstance(renderer, DeterministicDialogueRenderer)
        self.assertIsNotNone(notice)
        self.assertIn("OPENAI_API_KEY is missing", notice)


if __name__ == "__main__":
    unittest.main()
