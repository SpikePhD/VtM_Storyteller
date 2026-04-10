from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
import unittest

from vampire_storyteller.adventure_loader import (
    AdventureContentError,
    load_adv1_plot_investigation_rules,
    load_adv1_plot_progression_rules,
)
from vampire_storyteller.data_paths import ADVENTURE_ROOT


class AdventureRuleTests(unittest.TestCase):
    def test_rule_files_load_and_match_expected_values(self) -> None:
        progression_rules = load_adv1_plot_progression_rules()
        investigation_rules = load_adv1_plot_investigation_rules()

        self.assertEqual(progression_rules.plot_id, "plot_1")
        self.assertEqual(progression_rules.move_destination_id, "loc_church")
        self.assertEqual(progression_rules.wait_minimum_minutes, 60)
        self.assertEqual(investigation_rules.plot_id, "plot_1")
        self.assertEqual(investigation_rules.location_id, "loc_dock")
        self.assertTrue(investigation_rules.requires_roll)
        self.assertEqual(investigation_rules.roll_pool, 3)
        self.assertEqual(investigation_rules.difficulty, 4)

    def test_missing_rule_file_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir) / "ADV1"
            shutil.copytree(ADVENTURE_ROOT, temp_root)
            (temp_root / "plots" / "plot_resolution.json").unlink()

            with self.assertRaises(AdventureContentError) as ctx:
                load_adv1_plot_investigation_rules(temp_root)

        self.assertIn("Required adventure file missing", str(ctx.exception))

    def test_malformed_rule_file_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir) / "ADV1"
            shutil.copytree(ADVENTURE_ROOT, temp_root)
            (temp_root / "plots" / "plot_progression.json").write_text("{not valid json", encoding="utf-8")

            with self.assertRaises(AdventureContentError) as ctx:
                load_adv1_plot_progression_rules(temp_root)

        self.assertIn("Malformed adventure file", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
