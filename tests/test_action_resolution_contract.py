from __future__ import annotations

import unittest
from unittest.mock import patch

from vampire_storyteller.action_resolution import ActionResolutionKind
from vampire_storyteller.dice_engine import DeterministicCheckKind, DeterministicCheckResolution
from vampire_storyteller.game_session import GameSession


class ActionResolutionContractTests(unittest.TestCase):
    def test_blocked_investigate_populates_explicit_contract(self) -> None:
        session = GameSession()

        result = session.process_input("investigate")
        turn = session.get_last_action_resolution()

        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertEqual(turn.normalized_action.command_text, "investigate")
        self.assertEqual(turn.adjudication.resolution_kind, ActionResolutionKind.BLOCKED)
        self.assertIsNone(turn.check)
        self.assertEqual(turn.consequence_summary.messages, ())
        self.assertIn("Investigate is blocked", turn.output_text)
        self.assertEqual(result.output_text, turn.output_text)

    def test_automatic_status_uses_the_same_contract_shape(self) -> None:
        session = GameSession()

        result = session.process_input("status")
        turn = session.get_last_action_resolution()

        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertEqual(turn.normalized_action.command_text, "status")
        self.assertEqual(turn.adjudication.resolution_kind, ActionResolutionKind.AUTOMATIC)
        self.assertIsNone(turn.check)
        self.assertEqual(turn.consequence_summary.messages, ())
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
        self.assertEqual(turn.consequence_summary.messages, ("Plot 'Missing Ledger' resolved at North Dockside.",))
        self.assertIn("investigate_resolution_success", turn.consequence_summary.applied_effects)
        self.assertIn("plot_resolution_updated", turn.consequence_summary.applied_effects)
        self.assertIn("Plot 'Missing Ledger' resolved at North Dockside.", turn.output_text)
        self.assertEqual(result.output_text, turn.output_text)


if __name__ == "__main__":
    unittest.main()
