from __future__ import annotations

import unittest
from unittest.mock import patch

from vampire_storyteller.action_resolution import ActionBlockReason, ActionResolutionKind, NormalizationSource, TurnOutcomeKind
from vampire_storyteller.dice_engine import DeterministicCheckKind, DeterministicCheckResolution
from vampire_storyteller.dialogue_adjudication import DialogueAdjudicationResolutionKind
from vampire_storyteller.game_session import GameSession
from vampire_storyteller.social_models import SocialOutcomeKind, TopicResult


class ActionResolutionContractTests(unittest.TestCase):
    def test_blocked_investigate_populates_explicit_contract(self) -> None:
        session = GameSession()

        result = session.process_input("investigate")
        turn = session.get_last_action_resolution()

        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertEqual(turn.normalized_action.command_text, "investigate")
        self.assertEqual(turn.canonical_action_text, "investigate")
        self.assertEqual(turn.adjudication.resolution_kind, ActionResolutionKind.BLOCKED)
        self.assertIsNone(turn.check)
        self.assertEqual(turn.consequence_summary.messages, ())
        self.assertEqual(turn.turn_kind, TurnOutcomeKind.BLOCKED)
        self.assertFalse(turn.world_state_mutated)
        self.assertEqual(turn.block_reason, ActionBlockReason.PREREQUISITE_NOT_MET)
        self.assertIn("Investigate is blocked", turn.output_text)
        self.assertEqual(result.output_text, turn.output_text)

    def test_automatic_status_uses_the_same_contract_shape(self) -> None:
        session = GameSession()

        result = session.process_input("status")
        turn = session.get_last_action_resolution()

        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertEqual(turn.normalized_action.command_text, "status")
        self.assertEqual(turn.canonical_action_text, "status")
        self.assertEqual(turn.normalization_source, NormalizationSource.DIRECT_COMMAND)
        self.assertEqual(turn.adjudication.resolution_kind, ActionResolutionKind.AUTOMATIC)
        self.assertIsNone(turn.check)
        self.assertEqual(turn.consequence_summary.messages, ())
        self.assertEqual(turn.turn_kind, TurnOutcomeKind.NON_STATEFUL_ACTION)
        self.assertFalse(turn.world_state_mutated)
        self.assertEqual(result.output_text, turn.output_text)
        self.assertFalse(turn.render_scene)

    def test_roll_gated_investigate_populates_check_and_consequence_summary(self) -> None:
        session = GameSession()

        session.process_input("move loc_church")
        session.process_input("wait 60")
        session.process_input("move loc_dock")

        with patch("vampire_storyteller.game_session.resolve_deterministic_check") as mock_resolve:
            mock_resolve.return_value = DeterministicCheckResolution(
                kind=DeterministicCheckKind.INVESTIGATION,
                seed="2026-04-09T23:23:00+02:00|investigate|player_1",
                roll_pool=3,
                difficulty=4,
                individual_rolls=[7, 2, 9],
                successes=2,
                is_success=True,
            )
            result = session.process_input("investigate")

        turn = session.get_last_action_resolution()

        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertEqual(turn.adjudication.resolution_kind, ActionResolutionKind.ROLL_GATED)
        self.assertIsNotNone(turn.check)
        assert turn.check is not None
        self.assertEqual(turn.check.kind, DeterministicCheckKind.INVESTIGATION)
        self.assertEqual(turn.check.seed, "2026-04-09T23:23:00+02:00|investigate|player_1")
        self.assertEqual(turn.check.roll_pool, 3)
        self.assertEqual(turn.check.difficulty, 4)
        self.assertEqual(turn.check.successes, 2)
        self.assertTrue(turn.check.is_success)
        self.assertIsNotNone(turn.adjudication.check_spec)
        assert turn.adjudication.check_spec is not None
        self.assertEqual(turn.adjudication.check_spec.kind, DeterministicCheckKind.INVESTIGATION)
        self.assertEqual(turn.turn_kind, TurnOutcomeKind.STATEFUL_ACTION)
        self.assertTrue(turn.world_state_mutated)
        self.assertEqual(turn.consequence_summary.messages, ("Plot 'Missing Ledger' resolved at North Dockside.",))
        self.assertIn("investigate_resolution_success", turn.consequence_summary.applied_effects)
        self.assertIn("plot_resolution_updated", turn.consequence_summary.applied_effects)
        self.assertIn("Plot 'Missing Ledger' resolved at North Dockside.", turn.output_text)
        self.assertEqual(result.output_text, turn.output_text)

    def test_roll_gated_persuade_populates_check_and_dialogue_outcome(self) -> None:
        session = GameSession()

        with patch("vampire_storyteller.game_session.resolve_deterministic_check") as mock_resolve:
            mock_resolve.return_value = DeterministicCheckResolution(
                kind=DeterministicCheckKind.DIALOGUE_SOCIAL,
                seed="2026-04-09T22:00:00+02:00|talk|persuade|npc_1|dock|player_1|4|sensitive",
                roll_pool=3,
                difficulty=6,
                individual_rolls=[8, 2, 7],
                successes=2,
                is_success=True,
            )
            result = session.process_input("I persuade Jonas to help with the dock.")

        turn = session.get_last_action_resolution()

        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertEqual(turn.adjudication.resolution_kind, ActionResolutionKind.ROLL_GATED)
        self.assertIsNotNone(turn.check)
        assert turn.check is not None
        self.assertEqual(turn.check.kind, DeterministicCheckKind.DIALOGUE_SOCIAL)
        self.assertTrue(turn.check.is_success)
        self.assertIsNotNone(turn.dialogue_adjudication)
        assert turn.dialogue_adjudication is not None
        self.assertEqual(turn.dialogue_adjudication.resolution_kind, DialogueAdjudicationResolutionKind.ESCALATED)
        self.assertTrue(turn.dialogue_adjudication.check_required)
        self.assertEqual(turn.dialogue_adjudication.topic_status.value, "productive")
        self.assertIsNotNone(turn.social_outcome)
        assert turn.social_outcome is not None
        self.assertEqual(turn.social_outcome.outcome_kind, SocialOutcomeKind.REVEAL)
        self.assertEqual(turn.social_outcome.topic_result, TopicResult.OPENED)
        self.assertIsNotNone(turn.social_outcome.check_result)
        assert turn.social_outcome.check_result is not None
        self.assertTrue(turn.social_outcome.check_result.is_success)
        self.assertIn("dialogue_social_check_success", turn.social_outcome.state_effects)
        self.assertIn("dialogue_plot_progressed", turn.social_outcome.plot_effects)
        self.assertEqual(turn.turn_kind, TurnOutcomeKind.STATEFUL_ACTION)
        self.assertTrue(turn.world_state_mutated)
        self.assertIn("dialogue_social_check_success", turn.consequence_summary.applied_effects)
        self.assertIn("dock", result.output_text.lower())
        self.assertIn("trail", result.output_text.lower())
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "lead_confirmed")

    def test_refusal_path_populates_structured_social_outcome_packet(self) -> None:
        session = GameSession()

        result = session.process_input("Jonas, I don't believe you.")
        turn = session.get_last_action_resolution()

        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertTrue(result.output_text.strip())
        self.assertIsNotNone(turn.social_outcome)
        assert turn.social_outcome is not None
        self.assertEqual(turn.social_outcome.outcome_kind, SocialOutcomeKind.REFUSE)
        self.assertEqual(turn.social_outcome.topic_result, TopicResult.BLOCKED)
        self.assertTrue(turn.social_outcome.stance_shift.changed)


if __name__ == "__main__":
    unittest.main()
