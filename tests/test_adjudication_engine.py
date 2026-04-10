from __future__ import annotations

import unittest

from vampire_storyteller.adjudication_engine import adjudicate_command
from vampire_storyteller.command_models import HelpCommand, InvestigateCommand, LookCommand, MoveCommand, StatusCommand, WaitCommand
from vampire_storyteller.sample_world import build_sample_world
from vampire_storyteller.map_engine import move_player
from vampire_storyteller.plot_engine import advance_plots
from vampire_storyteller.actions import wait_action


class AdjudicationEngineTests(unittest.TestCase):
    def test_investigate_at_dock_with_confirmed_lead_requires_roll(self) -> None:
        world = build_sample_world()
        move_player(world, "loc_church")
        advance_plots(world, MoveCommand(destination_id="loc_church"))
        wait_action(world, 60)
        advance_plots(world, WaitCommand(minutes=60))
        move_player(world, "loc_dock")

        decision = adjudicate_command(world, InvestigateCommand())

        self.assertTrue(decision.requires_roll)
        self.assertEqual(decision.roll_pool, 3)
        self.assertEqual(decision.difficulty, 4)
        self.assertIn("lead_confirmed", decision.reason)

    def test_other_supported_commands_do_not_require_roll(self) -> None:
        world = build_sample_world()

        self.assertFalse(adjudicate_command(world, LookCommand()).requires_roll)
        self.assertFalse(adjudicate_command(world, MoveCommand(destination_id="loc_church")).requires_roll)
        self.assertFalse(adjudicate_command(world, WaitCommand(minutes=30)).requires_roll)
        self.assertFalse(adjudicate_command(world, HelpCommand()).requires_roll)
        self.assertFalse(adjudicate_command(world, StatusCommand()).requires_roll)

    def test_investigate_without_target_state_does_not_require_roll(self) -> None:
        world = build_sample_world()

        decision = adjudicate_command(world, InvestigateCommand())

        self.assertFalse(decision.requires_roll)
        self.assertIsNone(decision.roll_pool)
        self.assertIsNone(decision.difficulty)
        self.assertIsNotNone(decision.blocked_feedback)
        self.assertIn("blocked", decision.blocked_feedback.lower())
        self.assertIn("Missing Ledger", decision.blocked_feedback)

    def test_investigate_while_stage_is_church_visited_but_not_ready_still_blocks(self) -> None:
        world = build_sample_world()
        move_player(world, "loc_church")
        advance_plots(world, MoveCommand(destination_id="loc_church"))
        move_player(world, "loc_dock")

        decision = adjudicate_command(world, InvestigateCommand())

        self.assertFalse(decision.requires_roll)
        self.assertIsNotNone(decision.blocked_feedback)
        self.assertIn("lead_confirmed", decision.blocked_feedback)


if __name__ == "__main__":
    unittest.main()
