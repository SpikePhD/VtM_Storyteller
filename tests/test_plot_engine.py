from __future__ import annotations

import unittest

from vampire_storyteller.command_models import MoveCommand, TalkCommand, WaitCommand
from vampire_storyteller.dialogue_fact_authorization import apply_authorized_fact_progression
from vampire_storyteller.dialogue_fact_cards import DialogueFactCard
from vampire_storyteller.game_session import GameSession
from vampire_storyteller.map_engine import move_player
from vampire_storyteller.plot_engine import advance_plots
from vampire_storyteller.sample_world import build_sample_world
from vampire_storyteller.models import PlotThread
from vampire_storyteller.social_models import SocialOutcomeKind, SocialOutcomePacket, SocialStanceShift, TopicResult
from vampire_storyteller.command_models import ConversationStance
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

        move_result = session.process_input("/move loc_church")
        self.assertIn("The Missing Ledger has a church-records angle in play.", move_result.output_text)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "church_visited")

        wait_result = session.process_input("/wait 60")
        self.assertIn("The Missing Ledger has a confirmed lead.", wait_result.output_text)
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
        self.assertIn("The Missing Ledger has a church-records angle in play.", scene_text)

    def test_authorized_fact_progression_applies_reusable_backend_effects(self) -> None:
        world = build_sample_world()
        world.plots["plot_dummy"] = PlotThread(id="plot_dummy", name="Dummy Lead", stage="intro", active=True)
        fact_card = DialogueFactCard(
            fact_id="dummy_actionable_fact",
            kind="lead",
            summary="A reusable dummy lead reveal advances a custom plot stage.",
            plot_id="plot_dummy",
            reveal_plot_stage="resolved",
            reveal_story_flags=("dummy_lead_revealed",),
        )
        social_outcome = SocialOutcomePacket(
            outcome_kind=SocialOutcomeKind.REVEAL,
            stance_shift=SocialStanceShift(
                from_stance=ConversationStance.NEUTRAL,
                to_stance=ConversationStance.NEUTRAL,
            ),
            check_required=False,
            check_result=None,
            topic_result=TopicResult.OPENED,
            state_effects=(),
            plot_effects=(),
            reason_code="dummy_lead_reveal",
        )

        summary = apply_authorized_fact_progression(world, (fact_card,), social_outcome)

        self.assertEqual(world.plots["plot_dummy"].stage, "resolved")
        self.assertIn("dummy_lead_revealed", world.story_flags)
        self.assertIn("dummy_actionable_fact_plot_stage_revealed", summary.applied_effects)


if __name__ == "__main__":
    unittest.main()
