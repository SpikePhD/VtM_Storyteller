from __future__ import annotations

import unittest
from unittest.mock import patch

from vampire_storyteller.dice_engine import DeterministicCheckKind, DeterministicCheckResolution
from vampire_storyteller.dialogue_adjudication import DialogueAdjudicationResolutionKind, DialogueTopicStatus
from vampire_storyteller.dialogue_domain import DialogueDomain
from vampire_storyteller.game_session import GameSession
from vampire_storyteller.input_interpreter import InterpretedInput
from vampire_storyteller.social_models import SocialOutcomeKind, TopicResult


class FailingDialogueRenderer:
    def render_dialogue(self, render_input) -> str:
        raise RuntimeError("dialogue renderer failed")


class DialogueEndToEndTests(unittest.TestCase):
    def _run_dialogue_turn(self, session: GameSession, raw_input: str):
        result = session.process_input(raw_input)
        interpreted = session.get_last_interpreted_input()
        turn = session.get_last_action_resolution()

        self.assertIsNotNone(interpreted)
        self.assertIsNotNone(turn)
        assert interpreted is not None
        assert turn is not None
        self.assertIsNotNone(turn.dialogue_adjudication)
        self.assertIsNotNone(turn.social_outcome)
        assert turn.dialogue_adjudication is not None
        assert turn.social_outcome is not None
        return result, interpreted, turn

    def test_jonas_greeting_remains_allowed_without_revealing_the_lead(self) -> None:
        session = GameSession()

        result, interpreted, turn = self._run_dialogue_turn(session, "Jonas, hello")

        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertEqual(turn.dialogue_adjudication.resolution_kind, DialogueAdjudicationResolutionKind.ALLOWED)
        self.assertEqual(turn.dialogue_adjudication.topic_status, DialogueTopicStatus.AVAILABLE)
        self.assertEqual(turn.social_outcome.outcome_kind, SocialOutcomeKind.COOPERATE)
        self.assertEqual(turn.social_outcome.topic_result, TopicResult.UNCHANGED)
        self.assertFalse(turn.social_outcome.check_required)
        self.assertIn("nod", result.output_text.lower())
        self.assertNotIn("paper trail", result.output_text.lower())
        self.assertNotIn("waterline", result.output_text.lower())

    def test_jonas_small_talk_stays_polite_without_opening_the_lead(self) -> None:
        session = GameSession()

        session.process_input("Jonas, hello")
        result, interpreted, turn = self._run_dialogue_turn(session, "How are you?")

        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertIn("holding up", result.output_text.lower())
        self.assertIn("something specific", result.output_text.lower())
        self.assertNotIn("paper trail", result.output_text.lower())
        self.assertNotIn("waterline", result.output_text.lower())

    def test_jonas_dock_question_emits_productive_packet_from_backend_truth(self) -> None:
        session = GameSession()

        result, interpreted, turn = self._run_dialogue_turn(session, "Jonas, what happened at the dock?")

        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.LEAD_TOPIC)
        self.assertEqual(turn.dialogue_adjudication.topic_status, DialogueTopicStatus.PRODUCTIVE)
        self.assertEqual(turn.social_outcome.outcome_kind, SocialOutcomeKind.REVEAL)
        self.assertEqual(turn.social_outcome.topic_result, TopicResult.OPENED)
        self.assertFalse(turn.social_outcome.check_required)
        self.assertEqual(turn.social_outcome.plot_effects, ())
        self.assertEqual(turn.social_outcome.state_effects, ())
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")
        self.assertIn("dock", result.output_text.lower())
        self.assertIn("paper trail", result.output_text.lower())

    def test_jonas_persuade_success_renders_reveal_and_backend_progression(self) -> None:
        session = GameSession()

        with patch("vampire_storyteller.game_session.resolve_deterministic_check") as mock_resolve:
            mock_resolve.return_value = DeterministicCheckResolution(
                kind=DeterministicCheckKind.DIALOGUE_SOCIAL,
                seed="seed",
                roll_pool=3,
                difficulty=6,
                individual_rolls=[7, 8, 2],
                successes=2,
                is_success=True,
            )
            result, interpreted, turn = self._run_dialogue_turn(session, "I persuade Jonas to help with the dock.")

        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertEqual(turn.check.kind, DeterministicCheckKind.DIALOGUE_SOCIAL)
        self.assertTrue(turn.check.is_success)
        self.assertTrue(turn.social_outcome.check_result is not None and turn.social_outcome.check_result.is_success)
        self.assertEqual(turn.social_outcome.outcome_kind, SocialOutcomeKind.REVEAL)
        self.assertEqual(turn.social_outcome.topic_result, TopicResult.OPENED)
        self.assertIn("dialogue_social_check_success", turn.social_outcome.state_effects)
        self.assertIn("dialogue_plot_progressed", turn.social_outcome.plot_effects)
        self.assertIn("dialogue_social_check_success", turn.consequence_summary.applied_effects)
        self.assertIn("dialogue_plot_progressed", turn.consequence_summary.applied_effects)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "lead_confirmed")
        self.assertIn("jonas_shared_dock_lead", session.get_world_state().story_flags)
        self.assertTrue(
            any(token in result.output_text.lower() for token in ("waterline", "paper trail", "broker"))
        )

    def test_jonas_persuade_failure_renders_guarded_refusal_without_reveal(self) -> None:
        session = GameSession()

        with patch("vampire_storyteller.game_session.resolve_deterministic_check") as mock_resolve:
            mock_resolve.return_value = DeterministicCheckResolution(
                kind=DeterministicCheckKind.DIALOGUE_SOCIAL,
                seed="seed",
                roll_pool=3,
                difficulty=6,
                individual_rolls=[2, 3, 4],
                successes=0,
                is_success=False,
            )
            result, interpreted, turn = self._run_dialogue_turn(session, "I persuade Jonas to help with the dock.")

        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertTrue(turn.check is not None and not turn.check.is_success)
        self.assertTrue(turn.social_outcome.check_result is not None and not turn.social_outcome.check_result.is_success)
        self.assertEqual(turn.social_outcome.outcome_kind, SocialOutcomeKind.REFUSE)
        self.assertEqual(turn.social_outcome.topic_result, TopicResult.PARTIAL)
        self.assertEqual(turn.social_outcome.state_effects, ("dialogue_social_check_failure",))
        self.assertEqual(turn.social_outcome.plot_effects, ())
        self.assertNotIn("waterline", result.output_text.lower())
        self.assertNotIn("paper trail", result.output_text.lower())
        self.assertIn("guarded", result.output_text.lower())
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")
        self.assertEqual(session.get_world_state().story_flags, [])

    def test_aggressive_follow_up_stays_guarded_and_not_productive(self) -> None:
        session = GameSession()

        session.process_input("Jonas, what happened at the dock?")
        result, interpreted, turn = self._run_dialogue_turn(session, "I don't believe you.")

        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.LEAD_PRESSURE)
        self.assertEqual(turn.dialogue_adjudication.topic_status, DialogueTopicStatus.REFUSED)
        self.assertEqual(turn.social_outcome.outcome_kind, SocialOutcomeKind.REFUSE)
        self.assertEqual(turn.social_outcome.topic_result, TopicResult.BLOCKED)
        self.assertEqual(turn.social_outcome.state_effects, ())
        self.assertEqual(turn.social_outcome.plot_effects, ())
        self.assertIn("guarded", result.output_text.lower())
        self.assertNotIn("paper trail", result.output_text.lower())
        self.assertNotEqual(turn.dialogue_adjudication.topic_status, DialogueTopicStatus.PRODUCTIVE)

    def test_renderer_failure_returns_explicit_safe_error_when_main_renderer_raises(self) -> None:
        session = GameSession(dialogue_renderer=FailingDialogueRenderer())

        result, _, turn = self._run_dialogue_turn(session, "Jonas, what happened at the dock?")

        self.assertIn("dialogue rendering failed", result.output_text.lower())
        self.assertEqual(turn.social_outcome.outcome_kind, SocialOutcomeKind.REVEAL)

    def test_malformed_interpreted_dialogue_payload_cannot_mutate_world_state(self) -> None:
        session = GameSession()
        before = (
            session.get_world_state().player.location_id,
            session.get_world_state().plots["plot_1"].stage,
            tuple(session.get_world_state().story_flags),
            session.get_world_state().npcs["npc_1"].trust_level,
            session.get_conversation_focus_npc_id(),
            session.get_conversation_stance(),
            session.get_conversation_subtopic(),
        )

        malformed_interpretation = InterpretedInput(
            normalized_intent="talk",
            target_text="Jonas",
            target_reference="npc_1",
            canonical_command="talk",
            confidence=1.0,
            match_reason="malformed test payload",
            fallback_to_parser=False,
            dialogue_metadata=None,
        )

        with patch.object(session._input_interpreter, "interpret", return_value=malformed_interpretation):
            result = session.process_input("Jonas, hello")

        after = (
            session.get_world_state().player.location_id,
            session.get_world_state().plots["plot_1"].stage,
            tuple(session.get_world_state().story_flags),
            session.get_world_state().npcs["npc_1"].trust_level,
            session.get_conversation_focus_npc_id(),
            session.get_conversation_stance(),
            session.get_conversation_subtopic(),
        )

        self.assertIn("could not be parsed", result.output_text)
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
