from __future__ import annotations

import unittest

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
            session.process_input("inspect")

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
            "look\nstatus\nhelp\nmove <destination_id>\nwait <minutes>\ninvestigate\nsave\nload\nquit",
        )
        self.assertIn("Player:", status_result.output_text)
        self.assertTrue(quit_result.should_quit)
        self.assertEqual(provider.rendered_world_times, [])


if __name__ == "__main__":
    unittest.main()
