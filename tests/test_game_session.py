from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from vampire_storyteller.command_dispatcher import execute_command
from vampire_storyteller.command_models import ConversationStance, DialogueAct, TalkCommand
from vampire_storyteller.command_result import CommandResult
from vampire_storyteller.exceptions import CommandParseError
from vampire_storyteller.game_session import GameSession
from vampire_storyteller.narrative_provider import SceneNarrativeProvider
from vampire_storyteller.world_state import WorldState


class RecordingSceneProvider(SceneNarrativeProvider):
    def __init__(self) -> None:
        self.rendered_world_times: list[str] = []

    def render_scene(self, world_state: WorldState) -> str:
        self.rendered_world_times.append(world_state.current_time)
        return f"rendered:{world_state.current_time}"


class GameSessionTests(unittest.TestCase):
    def test_default_session_builds_successfully(self) -> None:
        session = GameSession()
        world = session.get_world_state()
        self.assertIsNotNone(world)
        self.assertEqual(world.player.name, "Mara Vale")
        self.assertEqual(world.player.location_id, "loc_cafe")
        self.assertEqual(world.player.hunger, 2)
        self.assertEqual(world.player.stats["strength"], 2)

    def test_startup_text_is_non_empty(self) -> None:
        session = GameSession()
        self.assertTrue(session.get_startup_text().strip())

    def test_look_returns_non_quit_result(self) -> None:
        session = GameSession()
        result = session.process_input("look")

        self.assertIsInstance(result, CommandResult)
        self.assertFalse(result.should_quit)
        self.assertTrue(result.output_text.strip())

    def test_move_updates_session_world_state(self) -> None:
        session = GameSession()
        session.process_input("move loc_church")

        world = session.get_world_state()
        self.assertEqual(world.player.location_id, "loc_church")
        self.assertEqual(world.current_time, "2026-04-09T22:08:00+02:00")

    def test_wait_updates_hunger_and_time(self) -> None:
        session = GameSession()
        session.process_input("wait 60")

        world = session.get_world_state()
        self.assertEqual(world.current_time, "2026-04-09T23:00:00+02:00")
        self.assertEqual(world.player.hunger, 3)

    def test_quit_returns_should_quit_true(self) -> None:
        session = GameSession()
        result = session.process_input("quit")
        self.assertTrue(result.should_quit)

    def test_parse_errors_propagate(self) -> None:
        session = GameSession()
        with self.assertRaises(CommandParseError):
            session.process_input("sing a song")

    def test_investigate_while_premature_returns_explicit_feedback(self) -> None:
        session = GameSession()

        result = session.process_input("investigate")

        self.assertIn("Investigate is blocked", result.output_text)
        self.assertIn("Missing Ledger", result.output_text)
        self.assertIn("lead_confirmed", result.output_text)
        self.assertFalse(result.render_scene)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")
        self.assertEqual(len(session.get_world_state().event_log), 0)

    def test_investigate_at_dock_before_lead_confirmed_returns_explicit_feedback(self) -> None:
        session = GameSession()

        session.process_input("move loc_church")
        session.process_input("move loc_dock")
        result = session.process_input("investigate")

        self.assertIn("Investigate is blocked", result.output_text)
        self.assertIn("lead_confirmed", result.output_text)
        self.assertFalse(result.render_scene)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "church_visited")

    def test_talk_to_present_npc_returns_authored_dialogue(self) -> None:
        session = GameSession()

        result = session.process_input("talk npc_1")

        self.assertIn("Jonas Reed keeps his voice low", result.output_text)
        self.assertFalse(result.render_scene)
        self.assertEqual(session.get_world_state().player.location_id, "loc_cafe")
        self.assertEqual(session.get_world_state().npcs["npc_1"].trust_level, 1)
        self.assertEqual(session.get_conversation_focus_npc_id(), "npc_1")
        self.assertEqual(session.get_conversation_stance(), ConversationStance.NEUTRAL)
        self.assertIn("trust: 1", session.get_startup_text())

    def test_talk_greeting_uses_dialogue_metadata(self) -> None:
        session = GameSession()

        result = session.process_input("Jonas, good evening.")

        self.assertIn("gives a brief nod", result.output_text)
        self.assertNotIn("keeps his voice low", result.output_text)
        self.assertEqual(session.get_world_state().npcs["npc_1"].trust_level, 0)

    def test_follow_up_uses_conversation_focus(self) -> None:
        session = GameSession()

        session.process_input("Jonas, good evening.")
        result = session.process_input("Why?")
        interpreted = session.get_last_interpreted_input()

        self.assertIn("hears 'Why?'", result.output_text)
        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertEqual(interpreted.dialogue_metadata.dialogue_act, DialogueAct.ASK)
        self.assertEqual(session.get_conversation_focus_npc_id(), "npc_1")

    def test_follow_up_unknownish_line_still_targets_focus(self) -> None:
        session = GameSession()

        session.process_input("Jonas, good evening.")
        result = session.process_input("I don't believe you.")
        interpreted = session.get_last_interpreted_input()

        self.assertIn("cuts the accusation off", result.output_text)
        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertEqual(interpreted.dialogue_metadata.dialogue_act, DialogueAct.ACCUSE)
        self.assertEqual(session.get_world_state().story_flags, [])
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")
        self.assertEqual(session.get_conversation_stance(), ConversationStance.GUARDED)

    def test_follow_up_what_do_you_mean_stays_in_question_path(self) -> None:
        session = GameSession()

        session.process_input("Jonas, good evening.")
        result = session.process_input("What do you mean?")
        interpreted = session.get_last_interpreted_input()

        self.assertIn("hears 'What do you mean?'", result.output_text)
        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertEqual(interpreted.dialogue_metadata.dialogue_act, DialogueAct.ASK)
        self.assertEqual(session.get_conversation_stance(), ConversationStance.NEUTRAL)

    def test_guarded_follow_up_go_on_does_not_unlock_productive_progression(self) -> None:
        session = GameSession()

        session.process_input("Jonas, good evening.")
        session.process_input("I don't believe you.")
        result = session.process_input("Go on.")

        self.assertNotIn("paper trail", result.output_text)
        self.assertNotIn("advanced from hook to lead_confirmed", result.output_text)
        self.assertEqual(session.get_world_state().story_flags, [])
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")
        self.assertEqual(session.get_conversation_stance(), ConversationStance.GUARDED)

    def test_talk_question_uses_preserved_utterance_text(self) -> None:
        session = GameSession()

        result = session.process_input("I ask Jonas what happened here.")
        interpreted = session.get_last_interpreted_input()

        self.assertIsNotNone(interpreted)
        self.assertIsNotNone(interpreted.dialogue_metadata)
        self.assertIn("I ask Jonas what happened here.", interpreted.dialogue_metadata.utterance_text)
        self.assertIn("hears 'what happened here.'", result.output_text)
        self.assertEqual(session.get_world_state().npcs["npc_1"].trust_level, 0)

    def test_aggressive_talk_is_guarded(self) -> None:
        session = GameSession()

        accuse_result = session.process_input("I accuse Jonas of hiding something.")
        threaten_result = session.process_input("I threaten Jonas to talk.")

        self.assertIn("cuts the accusation off", accuse_result.output_text)
        self.assertIn("ends the exchange", threaten_result.output_text)
        self.assertEqual(session.get_world_state().npcs["npc_1"].trust_level, 0)

    def test_move_clears_conversation_focus(self) -> None:
        session = GameSession()

        session.process_input("talk npc_1")
        session.process_input("move loc_church")

        self.assertIsNone(session.get_conversation_focus_npc_id())
        self.assertEqual(session.get_conversation_stance(), ConversationStance.NEUTRAL)
        with self.assertRaises(CommandParseError):
            session.process_input("Why?")

    def test_load_clears_conversation_focus_and_stance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir) / "save.json"
            session = GameSession(save_path=save_path)

            session.process_input("talk npc_1")
            session.process_input("load")

            self.assertIsNone(session.get_conversation_focus_npc_id())
            self.assertEqual(session.get_conversation_stance(), ConversationStance.NEUTRAL)

    def test_explicit_other_npc_replaces_focus_when_available(self) -> None:
        session = GameSession()

        session.process_input("talk npc_1")
        session.process_input("move loc_church")
        result = session.process_input("Sister Eliza, good evening.")
        interpreted = session.get_last_interpreted_input()

        self.assertIn("Sister Eliza", result.output_text)
        self.assertEqual(interpreted.target_reference, "npc_2")
        self.assertEqual(session.get_conversation_focus_npc_id(), "npc_2")

    def test_talk_can_shift_response_after_trust_improves(self) -> None:
        session = GameSession()

        first_result = session.process_input("talk npc_1")
        second_result = session.process_input("talk npc_1")

        self.assertIn("keeps his voice low", first_result.output_text)
        self.assertIn("loosens his shoulders", second_result.output_text)
        self.assertIn("advanced from hook to lead_confirmed", second_result.output_text)
        self.assertEqual(session.get_world_state().npcs["npc_1"].trust_level, 1)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "lead_confirmed")
        self.assertEqual(session.get_world_state().story_flags, ["jonas_shared_dock_lead"])

    def test_talk_one_shot_trust_hooks_do_not_stack_indefinitely(self) -> None:
        session = GameSession()

        session.process_input("talk npc_1")
        session.process_input("talk npc_1")
        session.process_input("talk npc_1")

        self.assertEqual(session.get_world_state().npcs["npc_1"].trust_level, 1)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "lead_confirmed")
        self.assertEqual(session.get_world_state().story_flags, ["jonas_shared_dock_lead"])

    def test_talk_to_absent_npc_returns_explicit_feedback(self) -> None:
        session = GameSession()

        result = session.process_input("talk npc_2")

        self.assertIn("Talk is blocked", result.output_text)
        self.assertIn("Sister Eliza", result.output_text)
        self.assertFalse(result.render_scene)

    def test_canonical_talk_without_metadata_still_works(self) -> None:
        session = GameSession()

        result = execute_command(session.get_world_state(), TalkCommand(npc_id="npc_1"))

        self.assertIn("Jonas Reed keeps his voice low", result.output_text)
        self.assertFalse(result.render_scene)

    def test_talk_uses_blocked_feedback_when_no_hook_matches_state(self) -> None:
        session = GameSession()

        session.process_input("move loc_church")
        session.process_input("wait 60")
        session.process_input("move loc_dock")
        session.process_input("investigate")
        result = session.process_input("talk npc_1")

        self.assertIn("Talk is blocked", result.output_text)
        self.assertIn("said what he will say", result.output_text)
        self.assertFalse(result.render_scene)
        self.assertIn("trust: 1", session.get_startup_text())

    def test_successful_investigate_updates_relevant_trust(self) -> None:
        session = GameSession()

        session.process_input("move loc_church")
        session.process_input("wait 60")
        session.process_input("move loc_dock")
        result = session.process_input("investigate")

        self.assertTrue(result.render_scene)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "resolved")
        self.assertIn("Plot 'Missing Ledger' resolved at North Dockside.", result.output_text)
        self.assertIn("Learned: The ledger's path points back to a hidden broker operating through the dock.", result.output_text)
        self.assertIn("Closing beat: Mara leaves North Dockside with the ledger matter settled.", result.output_text)
        self.assertEqual(session.get_world_state().npcs["npc_1"].trust_level, 1)
        self.assertEqual(session.get_world_state().npcs["npc_2"].trust_level, 1)
        self.assertEqual(session.get_world_state().story_flags, [])

    def test_save_load_restores_trust_reflected_in_scene_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir) / "save.json"
            session = GameSession(save_path=save_path)

            session.process_input("talk npc_1")
            session.process_input("save")

            reloaded_session = GameSession(save_path=save_path)
            load_result = reloaded_session.process_input("load")

            self.assertEqual(reloaded_session.get_world_state().npcs["npc_1"].trust_level, 1)
            self.assertIn("trust: 1", reloaded_session.get_startup_text())
            self.assertNotIn("Closing beat:", load_result.output_text)

    def test_injected_scene_provider_is_used_for_startup_and_mutations(self) -> None:
        provider = RecordingSceneProvider()
        session = GameSession(scene_provider=provider)

        startup_text = session.get_startup_text()
        look_result = session.process_input("look")
        move_result = session.process_input("move loc_church")

        self.assertEqual(startup_text, "rendered:2026-04-09T22:00:00+02:00")
        self.assertEqual(look_result.output_text, "rendered:2026-04-09T22:00:00+02:00")
        self.assertEqual(move_result.output_text, "rendered:2026-04-09T22:08:00+02:00")
        self.assertEqual(
            provider.rendered_world_times[:3],
            ["2026-04-09T22:00:00+02:00", "2026-04-09T22:00:00+02:00", "2026-04-09T22:08:00+02:00"],
        )

    def test_injected_scene_provider_is_used_after_wait_when_npcs_move(self) -> None:
        provider = RecordingSceneProvider()
        session = GameSession(scene_provider=provider)

        result = session.process_input("wait 60")

        self.assertEqual(result.output_text, "rendered:2026-04-09T23:00:00+02:00")
        self.assertEqual(provider.rendered_world_times[-1], "2026-04-09T23:00:00+02:00")
        self.assertEqual(session.get_world_state().npcs["npc_1"].location_id, "loc_dock")

    def test_help_status_and_quit_bypass_scene_provider(self) -> None:
        provider = RecordingSceneProvider()
        session = GameSession(scene_provider=provider)

        help_result = session.process_input("help")
        status_result = session.process_input("status")
        quit_result = session.process_input("quit")

        self.assertEqual(
            help_result.output_text.strip(),
            "look\nstatus\nhelp\nmove <destination_id>\nwait <minutes>\ntalk <npc_id>\ninvestigate\nsave\nload\nquit",
        )
        self.assertIn("Player:", status_result.output_text)
        self.assertTrue(quit_result.should_quit)
        self.assertEqual(provider.rendered_world_times, [])


if __name__ == "__main__":
    unittest.main()
