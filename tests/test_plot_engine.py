from __future__ import annotations

import unittest

from vampire_storyteller.command_models import MoveCommand, TalkCommand, WaitCommand
from vampire_storyteller.game_session import GameSession
from vampire_storyteller.map_engine import move_player
from vampire_storyteller.plot_engine import advance_plots
from vampire_storyteller.sample_world import build_sample_world
from vampire_storyteller.text_renderers import render_scene_text
from vampire_storyteller.actions import wait_action


class PlotEngineTests(unittest.TestCase):
    def test_move_to_church_advances_hook_to_church_visited(self) -> None:
        world = build_sample_world()
        move_player(world, "loc_church")
        event_count_before = len(world.event_log)

        messages = advance_plots(world, MoveCommand(destination_id="loc_church"))

        self.assertEqual(world.plots["plot_1"].stage, "church_visited")
        self.assertEqual(messages, ["Plot 'Missing Ledger' advanced from hook to church_visited."])
        self.assertEqual(len(world.event_log), event_count_before + 1)
        self.assertEqual(world.event_log[-1].description, messages[0])

    def test_wait_sixty_at_church_advances_to_lead_confirmed(self) -> None:
        world = build_sample_world()
        move_player(world, "loc_church")
        advance_plots(world, MoveCommand(destination_id="loc_church"))
        wait_action(world, 60)
        event_count_before = len(world.event_log)

        messages = advance_plots(world, WaitCommand(minutes=60))

        self.assertEqual(world.plots["plot_1"].stage, "lead_confirmed")
        self.assertEqual(messages, ["Plot 'Missing Ledger' advanced from church_visited to lead_confirmed."])
        self.assertEqual(len(world.event_log), event_count_before + 1)
        self.assertEqual(world.event_log[-1].description, messages[0])

    def test_wait_outside_church_does_not_advance_plot(self) -> None:
        world = build_sample_world()
        move_player(world, "loc_church")
        advance_plots(world, MoveCommand(destination_id="loc_church"))
        move_player(world, "loc_cafe")
        wait_action(world, 60)
        event_count_before = len(world.event_log)

        messages = advance_plots(world, WaitCommand(minutes=60))

        self.assertEqual(world.plots["plot_1"].stage, "church_visited")
        self.assertEqual(messages, [])
        self.assertEqual(len(world.event_log), event_count_before)

    def test_repeating_triggering_action_does_not_readvance_stage(self) -> None:
        world = build_sample_world()
        move_player(world, "loc_church")
        first_messages = advance_plots(world, MoveCommand(destination_id="loc_church"))
        move_player(world, "loc_cafe")
        move_player(world, "loc_church")
        event_count_before = len(world.event_log)
        second_messages = advance_plots(world, MoveCommand(destination_id="loc_church"))

        self.assertEqual(first_messages, ["Plot 'Missing Ledger' advanced from hook to church_visited."])
        self.assertEqual(second_messages, [])
        self.assertEqual(world.plots["plot_1"].stage, "church_visited")
        self.assertEqual(len(world.event_log), event_count_before)

    def test_game_session_process_input_advances_plot(self) -> None:
        session = GameSession()

        move_result = session.process_input("move loc_church")
        self.assertIn("church_visited", move_result.output_text)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "church_visited")

        wait_result = session.process_input("wait 60")
        self.assertIn("lead_confirmed", wait_result.output_text)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "lead_confirmed")

    def test_talk_advances_hook_to_lead_confirmed_after_trust_builds(self) -> None:
        world = build_sample_world()
        first_messages = advance_plots(world, TalkCommand(npc_id="npc_1"))

        self.assertEqual(first_messages, [])
        self.assertEqual(world.plots["plot_1"].stage, "hook")
        self.assertEqual(world.npcs["npc_1"].trust_level, 0)
        self.assertEqual(world.story_flags, [])

        world.npcs["npc_1"].trust_level = 1
        world.add_story_flag("jonas_shared_dock_lead")
        event_count_before = len(world.event_log)
        second_messages = advance_plots(world, TalkCommand(npc_id="npc_1"))

        self.assertEqual(world.plots["plot_1"].stage, "lead_confirmed")
        self.assertEqual(second_messages, ["Plot 'Missing Ledger' advanced from hook to lead_confirmed."])
        self.assertEqual(len(world.event_log), event_count_before + 1)
        self.assertEqual(world.event_log[-1].description, second_messages[0])

    def test_scene_text_exposes_plot_stage(self) -> None:
        world = build_sample_world()
        self.assertEqual(world.plots["plot_1"].stage, "hook")
        move_player(world, "loc_church")
        advance_plots(world, MoveCommand(destination_id="loc_church"))

        scene_text = render_scene_text(world)
        self.assertIn("Missing Ledger [church_visited]", scene_text)


if __name__ == "__main__":
    unittest.main()
