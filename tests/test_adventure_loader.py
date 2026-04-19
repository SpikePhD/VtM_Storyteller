from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from vampire_storyteller.adventure_loader import (
    AdventureContentError,
    load_adv1_adventure_metadata,
    load_adv1_dialogue_hook_definitions,
    load_adv1_location_definitions,
    load_adv1_npc_definitions,
    load_adv1_player_seed_data,
    load_adv1_plot_progression_rules,
    load_adv1_plot_outcome_definitions,
    load_adv1_plot_thread_definitions,
    load_adv1_world_state,
    load_adv1_world_state_seed_data,
)
from vampire_storyteller.data_paths import ADVENTURE_ROOT
from vampire_storyteller.sample_world import build_sample_world


class AdventureLoaderTests(unittest.TestCase):
    def test_adventure_metadata_loader_reads_adv1_file(self) -> None:
        metadata = load_adv1_adventure_metadata()

        self.assertEqual(metadata.id, "ADV1")
        self.assertEqual(metadata.name, "ADV1")
        self.assertIn("Current sample adventure", metadata.description)
        self.assertEqual(metadata.starting_world_state_source, "adventures/ADV1 files")

    def test_seed_world_is_loaded_from_adv1_files(self) -> None:
        world = build_sample_world()

        self.assertEqual(world.player.name, "Mara Vale")
        self.assertEqual(world.player.location_id, "loc_cafe")
        self.assertEqual(world.player.stats["strength"], 2)
        self.assertEqual(world.current_time, "2026-04-09T22:00:00+02:00")
        self.assertEqual(world.locations["loc_cafe"].name, "Blackthorn Cafe")
        self.assertEqual(world.npcs["npc_1"].name, "Jonas Reed")
        self.assertEqual(world.plots["plot_1"].stage, "hook")

    def test_direct_loader_matches_expected_seed_values(self) -> None:
        world = load_adv1_world_state()

        self.assertEqual(world.player.clan, "Ventrue")
        self.assertEqual(world.locations["loc_dock"].danger_level, 4)
        self.assertEqual(world.locations["loc_cafe"].connected_locations, ["loc_church", "loc_dock"])
        self.assertEqual(world.locations["loc_church"].travel_time["loc_dock"], 15)
        self.assertEqual(world.npcs["npc_2"].location_id, "loc_church")
        self.assertEqual(world.npcs["npc_1"].schedule["late"], "loc_dock")
        self.assertEqual(world.npcs["npc_1"].traits["voice"], "quiet")
        self.assertEqual(world.plots["plot_1"].triggers, ["NPC mentions the ledger", "Player visits the dock"])

    def test_world_state_seed_loader_reads_adv1_file(self) -> None:
        world_seed = load_adv1_world_state_seed_data()

        self.assertEqual(world_seed.current_time, "2026-04-09T22:00:00+02:00")

    def test_player_seed_loader_reads_adv1_file(self) -> None:
        player_seed = load_adv1_player_seed_data()

        self.assertEqual(player_seed.player.id, "player_1")
        self.assertEqual(player_seed.player.name, "Mara Vale")
        self.assertEqual(player_seed.player.clan, "Ventrue")
        self.assertEqual(player_seed.player.profession, "Fixer")
        self.assertEqual(player_seed.player.hunger, 2)
        self.assertEqual(player_seed.player.health, 7)
        self.assertEqual(player_seed.player.willpower, 5)
        self.assertEqual(player_seed.player.humanity, 6)
        self.assertEqual(player_seed.player.inventory, ["phone", "lighter"])
        self.assertEqual(player_seed.player.location_id, "loc_cafe")
        self.assertEqual(player_seed.player.stats["dexterity"], 3)

    def test_location_definition_loader_reads_adv1_file(self) -> None:
        location_definitions = load_adv1_location_definitions()

        self.assertEqual([definition.id for definition in location_definitions], ["loc_cafe", "loc_church", "loc_dock"])
        self.assertEqual(location_definitions[0].danger_level, 2)
        self.assertEqual(location_definitions[1].connected_locations, ["loc_cafe", "loc_dock"])
        self.assertEqual(location_definitions[2].travel_time["loc_church"], 15)
        self.assertEqual(location_definitions[0].scene_hook, "Muted conversations and posted notices make the cafe a quiet place to ask questions.")
        self.assertEqual(location_definitions[1].notable_features, ["record shelves", "side chapel", "faded stonework"])
        self.assertEqual(location_definitions[2].flavor_tags, ["exposed", "industrial", "cold"])

    def test_npc_definition_loader_reads_adv1_file(self) -> None:
        npc_definitions = load_adv1_npc_definitions()

        self.assertEqual([definition.id for definition in npc_definitions], ["npc_1", "npc_2"])
        self.assertEqual(npc_definitions[0].starting_location_id, "loc_cafe")
        self.assertEqual(npc_definitions[1].attitude_to_player, "guarded")
        self.assertEqual(npc_definitions[0].trust_level, 0)
        self.assertEqual(npc_definitions[0].goals[0], "Keep his distance until Mara proves trustworthy")
        self.assertIn("dock", npc_definitions[0].investigation_hint)
        self.assertEqual(npc_definitions[1].goals[1], "Watch for anyone asking about the ledger")
        self.assertIn("ledger", npc_definitions[1].investigation_hint)

    def test_plot_thread_definition_loader_reads_adv1_file(self) -> None:
        plot_definitions = load_adv1_plot_thread_definitions()

        self.assertEqual([definition.id for definition in plot_definitions], ["plot_1"])
        self.assertEqual(plot_definitions[0].stage, "hook")
        self.assertEqual(plot_definitions[0].consequences, ["A hidden broker becomes interested"])

    def test_plot_outcome_definition_loader_reads_adv1_file(self) -> None:
        outcome_definitions = load_adv1_plot_outcome_definitions()

        self.assertEqual([definition.id for definition in outcome_definitions], ["plot_1"])
        self.assertEqual(outcome_definitions[0].resolved_event_text, "Plot 'Missing Ledger' resolved at North Dockside.")
        self.assertIn("hidden broker", outcome_definitions[0].learned_outcome)
        self.assertIn("North Dockside", outcome_definitions[0].closing_beat)

    def test_dialogue_hook_definition_loader_reads_adv1_file(self) -> None:
        hook_definitions = load_adv1_dialogue_hook_definitions()

        self.assertEqual([definition.hook_id for definition in hook_definitions], [
            "jonas_hook_trust_0",
            "jonas_hook_trust_0_greet",
            "jonas_hook_trust_0_ask",
            "jonas_hook_trust_0_accuse",
            "jonas_hook_trust_0_threaten",
            "jonas_hook_trust_1",
            "jonas_lead_confirmed",
            "eliza_church_visited_0",
            "eliza_church_visited_1",
        ])
        self.assertEqual(hook_definitions[0].required_plot_stage, "hook")
        self.assertIn("dock", hook_definitions[0].dialogue_text)
        self.assertIn("ready", hook_definitions[0].blocked_text)
        self.assertEqual(hook_definitions[1].required_dialogue_acts, ["greet"])
        self.assertEqual(hook_definitions[2].required_dialogue_acts, ["ask"])
        self.assertIn("{speech_text}", hook_definitions[2].dialogue_text)
        self.assertEqual(hook_definitions[3].required_dialogue_acts, ["accuse"])
        self.assertEqual(hook_definitions[4].required_dialogue_acts, ["threaten"])
        self.assertEqual(hook_definitions[5].story_flags_to_add, ["jonas_shared_dock_lead"])
        self.assertEqual(hook_definitions[5].minimum_trust_level, 1)
        self.assertEqual(hook_definitions[5].trust_delta, 0)
        self.assertFalse(hook_definitions[5].repeatable)
        self.assertIn("paper trail", hook_definitions[5].dialogue_text)

    def test_plot_progression_definition_loader_reads_talk_branch(self) -> None:
        progression = load_adv1_plot_progression_rules()

        self.assertEqual(progression.talk_from_stage, "hook")
        self.assertEqual(progression.talk_npc_id, "npc_1")
        self.assertEqual(progression.talk_location_id, "loc_cafe")
        self.assertEqual(progression.talk_minimum_trust_level, 1)
        self.assertEqual(progression.talk_required_story_flag, "jonas_shared_dock_lead")
        self.assertEqual(progression.talk_to_stage, "lead_confirmed")

    def test_missing_location_definition_file_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir) / "ADV1"
            self._copy_adv1_files(temp_root)
            (temp_root / "locations" / "locations.json").unlink()

            with self.assertRaises(AdventureContentError) as ctx:
                load_adv1_location_definitions(temp_root)

        self.assertIn("Required adventure file missing", str(ctx.exception))

    def test_malformed_location_definition_file_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir) / "ADV1"
            self._copy_adv1_files(temp_root)
            (temp_root / "locations" / "locations.json").write_text("{not valid json", encoding="utf-8")

            with self.assertRaises(AdventureContentError) as ctx:
                load_adv1_location_definitions(temp_root)

        self.assertIn("Malformed adventure file", str(ctx.exception))

    def test_missing_location_scene_hook_field_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir) / "ADV1"
            self._copy_adv1_files(temp_root)
            location_path = temp_root / "locations" / "locations.json"
            location_data = json.loads(location_path.read_text(encoding="utf-8"))
            del location_data["locations"][0]["scene_hook"]
            location_path.write_text(json.dumps(location_data, indent=2), encoding="utf-8")

            with self.assertRaises(AdventureContentError) as ctx:
                load_adv1_location_definitions(temp_root)

        self.assertIn("Adventure field 'scene_hook'", str(ctx.exception))

    def test_missing_location_notable_features_field_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir) / "ADV1"
            self._copy_adv1_files(temp_root)
            location_path = temp_root / "locations" / "locations.json"
            location_data = json.loads(location_path.read_text(encoding="utf-8"))
            del location_data["locations"][0]["notable_features"]
            location_path.write_text(json.dumps(location_data, indent=2), encoding="utf-8")

            with self.assertRaises(AdventureContentError) as ctx:
                load_adv1_location_definitions(temp_root)

        self.assertIn("Adventure field 'notable_features'", str(ctx.exception))

    def test_missing_location_flavor_tags_field_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir) / "ADV1"
            self._copy_adv1_files(temp_root)
            location_path = temp_root / "locations" / "locations.json"
            location_data = json.loads(location_path.read_text(encoding="utf-8"))
            del location_data["locations"][0]["flavor_tags"]
            location_path.write_text(json.dumps(location_data, indent=2), encoding="utf-8")

            with self.assertRaises(AdventureContentError) as ctx:
                load_adv1_location_definitions(temp_root)

        self.assertIn("Adventure field 'flavor_tags'", str(ctx.exception))

    def test_missing_world_state_seed_file_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir) / "ADV1"
            self._copy_adv1_files(temp_root)
            (temp_root / "world" / "world_state.json").unlink()

            with self.assertRaises(AdventureContentError) as ctx:
                load_adv1_world_state_seed_data(temp_root)

        self.assertIn("Required adventure file missing", str(ctx.exception))

    def test_malformed_world_state_seed_time_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir) / "ADV1"
            self._copy_adv1_files(temp_root)
            world_state_path = temp_root / "world" / "world_state.json"
            world_state_data = json.loads(world_state_path.read_text(encoding="utf-8"))
            world_state_data["current_time"] = "not-a-time"
            world_state_path.write_text(json.dumps(world_state_data, indent=2), encoding="utf-8")

            with self.assertRaises(AdventureContentError) as ctx:
                load_adv1_world_state(temp_root)

        self.assertIn("current_time", str(ctx.exception))

    def test_missing_talk_progression_field_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir) / "ADV1"
            self._copy_adv1_files(temp_root)
            progression_path = temp_root / "plots" / "plot_progression.json"
            progression_data = json.loads(progression_path.read_text(encoding="utf-8"))
            del progression_data["talk"]["required_story_flag"]
            progression_path.write_text(json.dumps(progression_data, indent=2), encoding="utf-8")

            with self.assertRaises(AdventureContentError) as ctx:
                load_adv1_plot_progression_rules(temp_root)

        self.assertIn("Adventure field 'required_story_flag'", str(ctx.exception))

    def test_missing_adv1_config_file_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir) / "ADV1"
            self._copy_adv1_files(temp_root)
            (temp_root / "config" / "adventure.json").unlink()

            with self.assertRaises(AdventureContentError) as ctx:
                load_adv1_adventure_metadata(temp_root)

        self.assertIn("Required adventure file missing", str(ctx.exception))

    def test_player_starting_location_must_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir) / "ADV1"
            self._copy_adv1_files(temp_root)
            player_path = temp_root / "world" / "player.json"
            player_data = json.loads(player_path.read_text(encoding="utf-8"))
            player_data["location_id"] = "loc_missing"
            player_path.write_text(json.dumps(player_data, indent=2), encoding="utf-8")

            with self.assertRaises(AdventureContentError) as ctx:
                load_adv1_world_state(temp_root)

        self.assertIn("Player starting location", str(ctx.exception))

    def test_missing_player_seed_file_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir) / "ADV1"
            self._copy_adv1_files(temp_root)
            (temp_root / "world" / "player.json").unlink()

            with self.assertRaises(AdventureContentError) as ctx:
                load_adv1_player_seed_data(temp_root)

        self.assertIn("Required adventure file missing", str(ctx.exception))

    def test_missing_npc_definition_file_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir) / "ADV1"
            self._copy_adv1_files(temp_root)
            (temp_root / "npcs" / "npcs.json").unlink()

            with self.assertRaises(AdventureContentError) as ctx:
                load_adv1_npc_definitions(temp_root)

        self.assertIn("Required adventure file missing", str(ctx.exception))

    def test_missing_plot_thread_definition_file_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir) / "ADV1"
            self._copy_adv1_files(temp_root)
            (temp_root / "plots" / "plot_threads.json").unlink()

            with self.assertRaises(AdventureContentError) as ctx:
                load_adv1_plot_thread_definitions(temp_root)

        self.assertIn("Required adventure file missing", str(ctx.exception))

    def test_missing_plot_outcome_definition_file_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir) / "ADV1"
            self._copy_adv1_files(temp_root)
            (temp_root / "plots" / "plot_outcomes.json").unlink()

            with self.assertRaises(AdventureContentError) as ctx:
                load_adv1_plot_outcome_definitions(temp_root)

        self.assertIn("Required adventure file missing", str(ctx.exception))

    def test_missing_dialogue_hook_definition_file_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir) / "ADV1"
            self._copy_adv1_files(temp_root)
            (temp_root / "npcs" / "dialogue_hooks.json").unlink()

            with self.assertRaises(AdventureContentError) as ctx:
                load_adv1_dialogue_hook_definitions(temp_root)

        self.assertIn("Required adventure file missing", str(ctx.exception))

    def test_missing_dialogue_hook_trust_fields_fail_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir) / "ADV1"
            self._copy_adv1_files(temp_root)
            hook_path = temp_root / "npcs" / "dialogue_hooks.json"
            hook_data = json.loads(hook_path.read_text(encoding="utf-8"))
            del hook_data["dialogue_hooks"][0]["minimum_trust_level"]
            hook_path.write_text(json.dumps(hook_data, indent=2), encoding="utf-8")

            with self.assertRaises(AdventureContentError) as ctx:
                load_adv1_dialogue_hook_definitions(temp_root)

        self.assertIn("Adventure field 'minimum_trust_level'", str(ctx.exception))

    def test_missing_dialogue_hook_repeatable_field_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir) / "ADV1"
            self._copy_adv1_files(temp_root)
            hook_path = temp_root / "npcs" / "dialogue_hooks.json"
            hook_data = json.loads(hook_path.read_text(encoding="utf-8"))
            del hook_data["dialogue_hooks"][0]["repeatable"]
            hook_path.write_text(json.dumps(hook_data, indent=2), encoding="utf-8")

            with self.assertRaises(AdventureContentError) as ctx:
                load_adv1_dialogue_hook_definitions(temp_root)

        self.assertIn("Adventure field 'repeatable'", str(ctx.exception))

    def test_malformed_world_state_seed_file_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir) / "ADV1"
            self._copy_adv1_files(temp_root)
            (temp_root / "world" / "world_state.json").write_text("{not valid json", encoding="utf-8")

            with self.assertRaises(AdventureContentError) as ctx:
                load_adv1_world_state_seed_data(temp_root)

        self.assertIn("Malformed adventure file", str(ctx.exception))

    def test_malformed_player_seed_file_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir) / "ADV1"
            self._copy_adv1_files(temp_root)
            (temp_root / "world" / "player.json").write_text("{not valid json", encoding="utf-8")

            with self.assertRaises(AdventureContentError) as ctx:
                load_adv1_player_seed_data(temp_root)

        self.assertIn("Malformed adventure file", str(ctx.exception))

    def test_malformed_npc_definition_file_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir) / "ADV1"
            self._copy_adv1_files(temp_root)
            (temp_root / "npcs" / "npcs.json").write_text("{not valid json", encoding="utf-8")

            with self.assertRaises(AdventureContentError) as ctx:
                load_adv1_npc_definitions(temp_root)

        self.assertIn("Malformed adventure file", str(ctx.exception))

    def test_missing_npc_goals_field_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir) / "ADV1"
            self._copy_adv1_files(temp_root)
            npc_path = temp_root / "npcs" / "npcs.json"
            npc_data = json.loads(npc_path.read_text(encoding="utf-8"))
            del npc_data["npcs"][0]["goals"]
            npc_path.write_text(json.dumps(npc_data, indent=2), encoding="utf-8")

            with self.assertRaises(AdventureContentError) as ctx:
                load_adv1_npc_definitions(temp_root)

        self.assertIn("Adventure field 'goals'", str(ctx.exception))

    def test_missing_npc_investigation_hint_field_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir) / "ADV1"
            self._copy_adv1_files(temp_root)
            npc_path = temp_root / "npcs" / "npcs.json"
            npc_data = json.loads(npc_path.read_text(encoding="utf-8"))
            del npc_data["npcs"][0]["investigation_hint"]
            npc_path.write_text(json.dumps(npc_data, indent=2), encoding="utf-8")

            with self.assertRaises(AdventureContentError) as ctx:
                load_adv1_npc_definitions(temp_root)

        self.assertIn("Adventure field 'investigation_hint'", str(ctx.exception))

    def test_missing_npc_trust_level_field_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir) / "ADV1"
            self._copy_adv1_files(temp_root)
            npc_path = temp_root / "npcs" / "npcs.json"
            npc_data = json.loads(npc_path.read_text(encoding="utf-8"))
            del npc_data["npcs"][0]["trust_level"]
            npc_path.write_text(json.dumps(npc_data, indent=2), encoding="utf-8")

            with self.assertRaises(AdventureContentError) as ctx:
                load_adv1_npc_definitions(temp_root)

        self.assertIn("Adventure field 'trust_level'", str(ctx.exception))

    def test_missing_npc_consumed_dialogue_hooks_field_round_trip_defaults_cleanly(self) -> None:
        world = build_sample_world()

        self.assertEqual(world.npcs["npc_1"].consumed_dialogue_hooks, [])

    def test_malformed_plot_thread_definition_file_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir) / "ADV1"
            self._copy_adv1_files(temp_root)
            (temp_root / "plots" / "plot_threads.json").write_text("{not valid json", encoding="utf-8")

            with self.assertRaises(AdventureContentError) as ctx:
                load_adv1_plot_thread_definitions(temp_root)

        self.assertIn("Malformed adventure file", str(ctx.exception))

    def test_malformed_plot_outcome_definition_file_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir) / "ADV1"
            self._copy_adv1_files(temp_root)
            (temp_root / "plots" / "plot_outcomes.json").write_text("{not valid json", encoding="utf-8")

            with self.assertRaises(AdventureContentError) as ctx:
                load_adv1_plot_outcome_definitions(temp_root)

        self.assertIn("Malformed adventure file", str(ctx.exception))

    def test_malformed_dialogue_hook_definition_file_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir) / "ADV1"
            self._copy_adv1_files(temp_root)
            (temp_root / "npcs" / "dialogue_hooks.json").write_text("{not valid json", encoding="utf-8")

            with self.assertRaises(AdventureContentError) as ctx:
                load_adv1_dialogue_hook_definitions(temp_root)

        self.assertIn("Malformed adventure file", str(ctx.exception))

    def _copy_adv1_files(self, target_root: Path) -> None:
        shutil.copytree(ADVENTURE_ROOT, target_root)


if __name__ == "__main__":
    unittest.main()
