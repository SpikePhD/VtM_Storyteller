from __future__ import annotations

import unittest

from vampire_storyteller.data_paths import (
    ADVENTURE_ID,
    ADVENTURE_ROOT,
    get_adventure_config_path,
    get_adventure_locations_seed_path,
    get_adventure_metadata_path,
    get_adventure_npcs_seed_path,
    get_adventure_notes_path,
    get_adventure_plot_threads_seed_path,
    get_adventure_player_seed_path,
    get_adventure_plots_seed_path,
    get_adventure_plot_progression_path,
    get_adventure_plot_resolution_path,
    get_adventure_root,
    get_adventure_world_state_seed_path,
    get_adventure_world_path,
    get_default_save_path,
)


class AdventurePathTests(unittest.TestCase):
    def test_adv1_root_and_named_paths_are_resolved(self) -> None:
        self.assertEqual(get_adventure_root(), ADVENTURE_ROOT)
        self.assertEqual(ADVENTURE_ROOT.parts[-2:], ("adventures", ADVENTURE_ID))
        self.assertEqual(get_adventure_config_path().parts[-4:], ("adventures", ADVENTURE_ID, "config", "adventure.json"))
        self.assertEqual(get_adventure_metadata_path().parts[-4:], ("adventures", ADVENTURE_ID, "config", "adventure.json"))
        self.assertEqual(get_adventure_world_path().parts[-2:], ("ADV1", "world"))
        self.assertEqual(get_adventure_player_seed_path().parts[-3:], ("ADV1", "world", "player.json"))
        self.assertEqual(get_adventure_world_state_seed_path().parts[-3:], ("ADV1", "world", "world_state.json"))
        self.assertEqual(get_adventure_locations_seed_path().parts[-4:], ("adventures", ADVENTURE_ID, "locations", "locations.json"))
        self.assertEqual(get_adventure_npcs_seed_path().parts[-4:], ("adventures", ADVENTURE_ID, "npcs", "npcs.json"))
        self.assertEqual(get_adventure_plot_threads_seed_path().parts[-4:], ("adventures", ADVENTURE_ID, "plots", "plot_threads.json"))
        self.assertEqual(get_adventure_plots_seed_path().parts[-4:], ("adventures", ADVENTURE_ID, "plots", "plot_threads.json"))
        self.assertEqual(get_adventure_plot_progression_path().parts[-4:], ("adventures", ADVENTURE_ID, "plots", "plot_progression.json"))
        self.assertEqual(get_adventure_plot_resolution_path().parts[-4:], ("adventures", ADVENTURE_ID, "plots", "plot_resolution.json"))
        self.assertEqual(get_adventure_notes_path().parts[-4:], ("adventures", ADVENTURE_ID, "notes", "README.md"))
        self.assertEqual(get_default_save_path().parts[-4:], ("adventures", ADVENTURE_ID, "saves", "current_save.json"))

    def test_adv1_scaffold_files_exist(self) -> None:
        self.assertTrue(get_adventure_config_path().exists())
        self.assertTrue(get_adventure_player_seed_path().exists())
        self.assertTrue(get_adventure_world_state_seed_path().exists())
        self.assertTrue(get_adventure_locations_seed_path().is_file())
        self.assertTrue(get_adventure_npcs_seed_path().is_file())
        self.assertTrue(get_adventure_plot_threads_seed_path().is_file())
        self.assertTrue(get_adventure_plot_progression_path().exists())
        self.assertTrue(get_adventure_plot_resolution_path().exists())
        self.assertTrue(get_adventure_notes_path().exists())
        self.assertTrue((ADVENTURE_ROOT / "world").exists())
        self.assertTrue((ADVENTURE_ROOT / "plots").exists())
        self.assertTrue((ADVENTURE_ROOT / "npcs").exists())
        self.assertTrue((ADVENTURE_ROOT / "locations").exists())
        self.assertTrue((ADVENTURE_ROOT / "saves").exists())


if __name__ == "__main__":
    unittest.main()
