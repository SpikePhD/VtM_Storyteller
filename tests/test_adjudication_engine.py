from __future__ import annotations

import unittest

from vampire_storyteller.action_resolution import ActionBlockReason, ActionResolutionKind
from vampire_storyteller.adjudication_engine import adjudicate_command
from vampire_storyteller.command_models import HelpCommand, InvestigateCommand, LookCommand, MoveCommand, StatusCommand, TalkCommand, WaitCommand
from vampire_storyteller.sample_world import build_sample_world
from vampire_storyteller.map_engine import move_player
from vampire_storyteller.plot_engine import advance_plots
from vampire_storyteller.actions import wait_action


class AdjudicationEngineTests(unittest.TestCase):
    def test_look_status_and_wait_are_automatic(self) -> None:
        world = build_sample_world()

        look_decision = adjudicate_command(world, LookCommand())
        status_decision = adjudicate_command(world, StatusCommand())
        wait_decision = adjudicate_command(world, WaitCommand(minutes=30))
        help_decision = adjudicate_command(world, HelpCommand())

        self.assertEqual(look_decision.resolution_kind, ActionResolutionKind.AUTOMATIC)
        self.assertEqual(status_decision.resolution_kind, ActionResolutionKind.AUTOMATIC)
        self.assertEqual(wait_decision.resolution_kind, ActionResolutionKind.AUTOMATIC)
        self.assertEqual(help_decision.resolution_kind, ActionResolutionKind.AUTOMATIC)
        self.assertFalse(look_decision.is_blocked)
        self.assertFalse(status_decision.is_blocked)
        self.assertFalse(wait_decision.is_blocked)
        self.assertFalse(help_decision.is_blocked)

    def test_move_to_connected_destination_is_automatic(self) -> None:
        world = build_sample_world()

        decision = adjudicate_command(world, MoveCommand(destination_id="loc_church"))

        self.assertEqual(decision.resolution_kind, ActionResolutionKind.AUTOMATIC)
        self.assertFalse(decision.requires_roll)
        self.assertIsNone(decision.block_reason)

    def test_move_to_missing_destination_is_blocked(self) -> None:
        world = build_sample_world()

        decision = adjudicate_command(world, MoveCommand(destination_id="loc_missing"))

        self.assertEqual(decision.resolution_kind, ActionResolutionKind.BLOCKED)
        self.assertEqual(decision.block_reason, ActionBlockReason.INVALID_DESTINATION)
        self.assertIsNotNone(decision.blocked_feedback)
        self.assertIn("destination 'loc_missing' does not exist", decision.blocked_feedback)

    def test_talk_to_absent_npc_is_blocked(self) -> None:
        world = build_sample_world()

        decision = adjudicate_command(world, TalkCommand(npc_id="npc_2"))

        self.assertEqual(decision.resolution_kind, ActionResolutionKind.BLOCKED)
        self.assertEqual(decision.block_reason, ActionBlockReason.TARGET_NOT_PRESENT)
        self.assertIsNotNone(decision.blocked_feedback)
        self.assertIn("Sister Eliza", decision.blocked_feedback)

    def test_investigate_without_target_state_is_blocked(self) -> None:
        world = build_sample_world()

        decision = adjudicate_command(world, InvestigateCommand())

        self.assertEqual(decision.resolution_kind, ActionResolutionKind.BLOCKED)
        self.assertEqual(decision.block_reason, ActionBlockReason.PREREQUISITE_NOT_MET)
        self.assertIsNotNone(decision.blocked_feedback)
        self.assertIn("lead_confirmed", decision.blocked_feedback)

    def test_investigate_at_dock_with_confirmed_lead_is_roll_gated(self) -> None:
        world = build_sample_world()
        move_player(world, "loc_church")
        advance_plots(world, MoveCommand(destination_id="loc_church"))
        wait_action(world, 60)
        advance_plots(world, WaitCommand(minutes=60))
        move_player(world, "loc_dock")

        decision = adjudicate_command(world, InvestigateCommand())

        self.assertEqual(decision.resolution_kind, ActionResolutionKind.ROLL_GATED)
        self.assertTrue(decision.requires_roll)
        self.assertEqual(decision.roll_pool, 3)
        self.assertEqual(decision.difficulty, 4)
        self.assertIn("lead_confirmed", decision.reason)


if __name__ == "__main__":
    unittest.main()
