from __future__ import annotations

import unittest

from vampire_storyteller.action_resolution import ActionAdjudicationOutcome, ActionCheckOutcome, ActionResolutionKind
from vampire_storyteller.command_models import InvestigateCommand, MoveCommand, WaitCommand
from vampire_storyteller.command_parser import parse_command
from vampire_storyteller.consequence_engine import apply_consequences, apply_post_resolution_consequences
from vampire_storyteller.game_session import GameSession
from vampire_storyteller.map_engine import move_player
from vampire_storyteller.plot_engine import advance_plots
from vampire_storyteller.sample_world import build_sample_world
from vampire_storyteller.actions import wait_action
from vampire_storyteller.exceptions import CommandParseError
from vampire_storyteller.dice_engine import DeterministicCheckKind, DeterministicCheckResolution, DiceRollResult
from unittest.mock import patch


class ConsequenceEngineTests(unittest.TestCase):
    def test_investigate_parses_successfully(self) -> None:
        command = parse_command("investigate")
        self.assertIsInstance(command, InvestigateCommand)

    def test_investigate_with_extra_args_fails(self) -> None:
        with self.assertRaises(CommandParseError):
            parse_command("investigate dock")

    def test_consequence_does_nothing_if_plot_is_not_at_lead_confirmed(self) -> None:
        world = build_sample_world()
        world.player.location_id = "loc_dock"

        messages = apply_consequences(world, InvestigateCommand())

        self.assertEqual(messages, [])
        self.assertTrue(world.plots["plot_1"].active)
        self.assertEqual(world.plots["plot_1"].stage, "hook")
        self.assertEqual(len(world.event_log), 0)

    def test_consequence_does_nothing_if_player_is_not_at_loc_dock(self) -> None:
        world = build_sample_world()
        move_player(world, "loc_church")
        advance_plots(world, MoveCommand(destination_id="loc_church"))
        wait_action(world, 60)
        advance_plots(world, WaitCommand(minutes=60))

        messages = apply_consequences(world, InvestigateCommand())

        self.assertEqual(messages, [])
        self.assertTrue(world.plots["plot_1"].active)
        self.assertEqual(world.plots["plot_1"].stage, "lead_confirmed")
        self.assertGreaterEqual(len(world.event_log), 4)

    def test_consequence_resolves_plot_on_successful_roll(self) -> None:
        world = build_sample_world()
        move_player(world, "loc_church")
        advance_plots(world, MoveCommand(destination_id="loc_church"))
        wait_action(world, 60)
        advance_plots(world, WaitCommand(minutes=60))
        move_player(world, "loc_dock")

        roll_result = DiceRollResult(
            pool=3,
            difficulty=6,
            individual_rolls=[7, 2, 9],
            successes=2,
            is_success=True,
        )
        messages = apply_consequences(world, InvestigateCommand(), roll_result=roll_result)

        self.assertEqual(messages, ["The Missing Ledger trail resolves at North Dockside."])
        self.assertFalse(world.plots["plot_1"].active)
        self.assertEqual(world.plots["plot_1"].stage, "resolved")
        self.assertEqual(world.plots["plot_1"].resolution_summary, "Mara finds the ledger trail at North Dockside.")
        self.assertIn("hidden broker", world.plots["plot_1"].learned_outcome)
        self.assertIn("Mara leaves North Dockside", world.plots["plot_1"].closing_beat)
        self.assertEqual(world.npcs["npc_1"].trust_level, 1)
        self.assertEqual(world.npcs["npc_2"].trust_level, 2)
        self.assertEqual(world.event_log[-1].description, "Mara leaves North Dockside with the ledger matter settled.")
        self.assertEqual(world.event_log[-2].description, "The Missing Ledger trail resolves at North Dockside.")
        self.assertEqual(world.event_log[-1].involved_entities, ["player_1", "plot_1", "loc_dock"])

    def test_consequence_failure_does_not_resolve_plot(self) -> None:
        world = build_sample_world()
        move_player(world, "loc_church")
        advance_plots(world, MoveCommand(destination_id="loc_church"))
        wait_action(world, 60)
        advance_plots(world, WaitCommand(minutes=60))
        move_player(world, "loc_dock")

        roll_result = DiceRollResult(
            pool=3,
            difficulty=6,
            individual_rolls=[2, 4, 5],
            successes=0,
            is_success=False,
        )
        messages = apply_consequences(world, InvestigateCommand(), roll_result=roll_result)

        self.assertEqual(messages, ["The search at North Dockside does not settle the Missing Ledger yet."])
        self.assertTrue(world.plots["plot_1"].active)
        self.assertEqual(world.plots["plot_1"].stage, "lead_confirmed")
        self.assertEqual(world.event_log[-1].description, "The search at North Dockside does not settle the Missing Ledger yet.")

    def test_post_resolution_consequences_return_structured_summary(self) -> None:
        world = build_sample_world()
        move_player(world, "loc_church")
        advance_plots(world, MoveCommand(destination_id="loc_church"))
        wait_action(world, 60)
        advance_plots(world, WaitCommand(minutes=60))
        move_player(world, "loc_dock")

        summary = apply_post_resolution_consequences(
            world,
            InvestigateCommand(),
            ActionAdjudicationOutcome(
                resolution_kind=ActionResolutionKind.ROLL_GATED,
                reason="test roll gating",
                roll_pool=3,
                difficulty=6,
            ),
            ActionCheckOutcome(
                kind=DeterministicCheckKind.INVESTIGATION,
                seed="2026-04-09T23:23:00+02:00|investigate|player_1",
                roll_pool=3,
                difficulty=6,
                individual_rolls=[7, 2, 9],
                successes=2,
                is_success=True,
            ),
        )

        self.assertEqual(summary.messages, ("The Missing Ledger trail resolves at North Dockside.",))
        self.assertIn("investigate_resolution_success", summary.applied_effects)
        self.assertIn("plot_resolution_updated", summary.applied_effects)
        self.assertIn("trust_adjustments_applied", summary.applied_effects)
        self.assertIn("closing_beat_logged", summary.applied_effects)
        self.assertFalse(world.plots["plot_1"].active)
        self.assertEqual(world.plots["plot_1"].stage, "resolved")

    def test_session_flow_resolves_hook_and_renders_resolution_state(self) -> None:
        session = GameSession()

        session.process_input("/move loc_church")
        session.process_input("/wait 60")
        session.process_input("/move loc_dock")
        with patch("vampire_storyteller.game_session.resolve_deterministic_check") as mock_resolve:
            mock_resolve.return_value = DeterministicCheckResolution(
                kind=DeterministicCheckKind.INVESTIGATION,
                seed="2026-04-09T23:23:00+02:00|investigate|player_1",
                roll_pool=3,
                difficulty=6,
                individual_rolls=[7, 2, 9],
                successes=2,
                is_success=True,
            )
            result = session.process_input("/investigate")
            mock_resolve.assert_called_once()

        world = session.get_world_state()
        self.assertFalse(world.plots["plot_1"].active)
        self.assertEqual(world.plots["plot_1"].stage, "resolved")
        self.assertIn("Mara finds the ledger trail at North Dockside.", result.output_text)
        self.assertIn("The ledger's path points back to a hidden broker operating through the dock.", result.output_text)
        self.assertIn("Mara leaves North Dockside with the ledger matter settled.", result.output_text)
        self.assertNotIn("Learned:", result.output_text)
        self.assertNotIn("Closing beat:", result.output_text)
        self.assertIn("Active Plots: None", result.output_text)
        self.assertIn("Recent Events:", result.output_text)
        self.assertNotIn("Rolled investigation check: 3 dice vs difficulty 6", result.output_text)
        self.assertTrue(any("Rolled investigation check: 3 dice vs difficulty 6" in entry.description for entry in world.event_log))
        self.assertEqual(world.plots["plot_1"].resolution_summary, "Mara finds the ledger trail at North Dockside.")

    def test_session_flow_failure_keeps_plot_active_and_logs_roll(self) -> None:
        session = GameSession()

        session.process_input("/move loc_church")
        session.process_input("/wait 60")
        session.process_input("/move loc_dock")
        with patch("vampire_storyteller.game_session.resolve_deterministic_check") as mock_resolve:
            mock_resolve.return_value = DeterministicCheckResolution(
                kind=DeterministicCheckKind.INVESTIGATION,
                seed="2026-04-09T23:23:00+02:00|investigate|player_1",
                roll_pool=3,
                difficulty=6,
                individual_rolls=[2, 4, 5],
                successes=0,
                is_success=False,
            )
            result = session.process_input("/investigate")
            mock_resolve.assert_called_once()

        world = session.get_world_state()
        self.assertTrue(world.plots["plot_1"].active)
        self.assertEqual(world.plots["plot_1"].stage, "lead_confirmed")
        self.assertIn("The search at North Dockside does not settle the Missing Ledger yet.", result.output_text)
        self.assertNotIn("Rolled investigation check: 3 dice vs difficulty 6", result.output_text)
        self.assertTrue(any("Rolled investigation check: 3 dice vs difficulty 6" in entry.description for entry in world.event_log))
        self.assertIn("Active Plots: Missing Ledger [lead_confirmed]", result.output_text)


if __name__ == "__main__":
    unittest.main()
