from __future__ import annotations

import unittest

from vampire_storyteller.game_session import GameSession
from vampire_storyteller.models import NPC, Player
from vampire_storyteller.npc_engine import get_time_band, update_npcs_for_current_time
from vampire_storyteller.sample_world import build_sample_world
from vampire_storyteller.world_state import WorldState


class NpcEngineTests(unittest.TestCase):
    def test_get_time_band_returns_expected_values(self) -> None:
        self.assertEqual(get_time_band("2026-04-09T18:00:00+02:00"), "evening")
        self.assertEqual(get_time_band("2026-04-09T21:00:00+02:00"), "night")
        self.assertEqual(get_time_band("2026-04-09T23:00:00+02:00"), "late")
        self.assertEqual(get_time_band("2026-04-10T01:00:00+02:00"), "midnight")
        self.assertIsNone(get_time_band("2026-04-09T16:59:59+02:00"))
        self.assertIsNone(get_time_band("not-a-timestamp"))

    def test_npcs_move_when_current_time_enters_scheduled_band(self) -> None:
        world = build_sample_world()
        world.current_time = "2026-04-09T23:00:00+02:00"

        messages = update_npcs_for_current_time(world)

        self.assertEqual(world.npcs["npc_1"].traits, {"voice": "quiet", "behavior": "observant"})
        self.assertEqual(world.npcs["npc_1"].location_id, "loc_dock")
        self.assertEqual(messages, ["Jonas Reed moved to North Dockside."])
        self.assertEqual(len(world.event_log), 1)
        self.assertEqual(
            world.event_log[0].description,
            "NPC 'Jonas Reed' moved to North Dockside for late.",
        )
        self.assertEqual(world.event_log[0].involved_entities, ["npc_1", "loc_dock"])

    def test_npcs_do_not_move_when_already_at_scheduled_location(self) -> None:
        world = build_sample_world()
        world.current_time = "2026-04-09T21:00:00+02:00"
        world.npcs["npc_1"].location_id = "loc_cafe"

        messages = update_npcs_for_current_time(world)

        self.assertEqual(messages, [])
        self.assertEqual(len(world.event_log), 0)
        self.assertEqual(world.npcs["npc_1"].location_id, "loc_cafe")

    def test_invalid_scheduled_location_ids_are_skipped_safely(self) -> None:
        world = WorldState(
            player=Player(
                id="player_1",
                name="Mara Vale",
                clan="Ventrue",
                profession="Fixer",
                hunger=2,
                health=7,
                willpower=5,
                humanity=6,
                location_id="loc_cafe",
            ),
            npcs={
                "npc_1": NPC(
                    id="npc_1",
                    name="Jonas Reed",
                    role="Informant",
                    location_id="loc_cafe",
                    attitude_to_player="wary",
                    schedule={"late": "loc_missing"},
                )
            },
            locations=build_sample_world().locations,
            current_time="2026-04-09T23:00:00+02:00",
        )

        messages = update_npcs_for_current_time(world)

        self.assertEqual(messages, [])
        self.assertEqual(world.npcs["npc_1"].location_id, "loc_cafe")
        self.assertEqual(len(world.event_log), 0)

    def test_npc_move_events_are_logged(self) -> None:
        world = build_sample_world()
        world.current_time = "2026-04-09T23:00:00+02:00"

        update_npcs_for_current_time(world)

        self.assertGreaterEqual(len(world.event_log), 1)
        self.assertTrue(world.event_log[-1].description.startswith("NPC 'Jonas Reed' moved to"))
        self.assertEqual(world.event_log[-1].timestamp, "2026-04-09T23:00:00+02:00")

    def test_game_session_wait_triggers_npc_movement(self) -> None:
        session = GameSession()

        result = session.process_input("wait 60")
        world = session.get_world_state()

        self.assertEqual(world.current_time, "2026-04-09T23:00:00+02:00")
        self.assertEqual(world.npcs["npc_1"].location_id, "loc_dock")
        self.assertIn("NPCs Present: None", result.output_text)
        self.assertIn("NPC 'Jonas Reed' moved to North Dockside for late.", result.output_text)

    def test_scene_output_reflects_npc_presence_after_time_advancement(self) -> None:
        session = GameSession()

        startup_text = session.get_startup_text()
        self.assertIn("NPCs Present: Jonas Reed (Informant, attitude: wary, trust: 0)", startup_text)

        result = session.process_input("wait 60")

        self.assertIn("NPCs Present: None", result.output_text)
        self.assertNotIn("Jonas Reed (Informant, attitude: wary)", result.output_text)


if __name__ == "__main__":
    unittest.main()
