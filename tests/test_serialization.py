from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from vampire_storyteller.models import EventLogEntry
from vampire_storyteller.serialization import load_world_state, save_world_state
from vampire_storyteller.sample_world import build_sample_world


class SerializationTests(unittest.TestCase):
    def test_world_state_saves_and_loads_successfully(self) -> None:
        world = build_sample_world()
        world.append_event(
            EventLogEntry(
                timestamp="2026-04-09T22:10:00+02:00",
                description="Test event",
                involved_entities=["player_1"],
            )
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "world.json"
            save_world_state(world, path)
            loaded_world = load_world_state(path)

        self.assertEqual(loaded_world.player.id, world.player.id)
        self.assertEqual(loaded_world.player.name, world.player.name)
        self.assertEqual(loaded_world.player.location_id, world.player.location_id)
        self.assertEqual(loaded_world.current_time, world.current_time)
        self.assertEqual(loaded_world.npcs["npc_1"].goals, world.npcs["npc_1"].goals)
        self.assertEqual(loaded_world.npcs["npc_1"].investigation_hint, world.npcs["npc_1"].investigation_hint)
        self.assertEqual(loaded_world.npcs["npc_1"].trust_level, world.npcs["npc_1"].trust_level)
        self.assertEqual(loaded_world.npcs["npc_1"].consumed_dialogue_hooks, world.npcs["npc_1"].consumed_dialogue_hooks)
        self.assertEqual(loaded_world.locations["loc_cafe"].scene_hook, world.locations["loc_cafe"].scene_hook)
        self.assertEqual(loaded_world.locations["loc_cafe"].notable_features, world.locations["loc_cafe"].notable_features)
        self.assertEqual(loaded_world.locations["loc_cafe"].flavor_tags, world.locations["loc_cafe"].flavor_tags)

    def test_event_log_round_trip_works(self) -> None:
        world = build_sample_world()
        world.append_event(
            EventLogEntry(
                timestamp="2026-04-09T22:10:00+02:00",
                description="Round-trip event",
                involved_entities=["player_1", "loc_cafe"],
            )
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "world.json"
            save_world_state(world, path)
            loaded_world = load_world_state(path)

        self.assertEqual(len(loaded_world.event_log), 1)
        self.assertEqual(loaded_world.event_log[0].description, "Round-trip event")
        self.assertEqual(loaded_world.event_log[0].involved_entities, ["player_1", "loc_cafe"])

    def test_location_player_and_plot_data_survive_round_trip(self) -> None:
        world = build_sample_world()
        world.npcs["npc_1"].trust_level = 2
        world.npcs["npc_1"].consumed_dialogue_hooks = ["jonas_hook_trust_0"]
        world.plots["plot_2"] = world.plots["plot_1"].__class__(
            id="plot_2",
            name="Second Hook",
            stage="hook",
            active=False,
            triggers=["trigger"],
            consequences=["consequence"],
        )
        world.plots["plot_1"].resolution_summary = "Plot 'Missing Ledger' resolved at North Dockside."
        world.plots["plot_1"].learned_outcome = "The ledger's path points back to a hidden broker operating through the dock."
        world.plots["plot_1"].closing_beat = "Mara leaves North Dockside with the ledger matter settled."

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "world.json"
            save_world_state(world, path)
            loaded_world = load_world_state(path)

        self.assertEqual(loaded_world.player.name, "Mara Vale")
        self.assertIn("loc_church", loaded_world.locations)
        self.assertEqual(loaded_world.locations["loc_cafe"].name, "Blackthorn Cafe")
        self.assertEqual(loaded_world.plots["plot_1"].name, "Missing Ledger")
        self.assertEqual(loaded_world.plots["plot_1"].resolution_summary, "Plot 'Missing Ledger' resolved at North Dockside.")
        self.assertIn("hidden broker", loaded_world.plots["plot_1"].learned_outcome)
        self.assertIn("Mara leaves North Dockside", loaded_world.plots["plot_1"].closing_beat)
        self.assertEqual(loaded_world.npcs["npc_1"].trust_level, 2)
        self.assertEqual(loaded_world.npcs["npc_1"].consumed_dialogue_hooks, ["jonas_hook_trust_0"])
        self.assertIn("plot_2", loaded_world.plots)
        self.assertFalse(loaded_world.plots["plot_2"].active)


if __name__ == "__main__":
    unittest.main()
