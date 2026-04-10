from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from vampire_storyteller.data_paths import get_default_save_path
from vampire_storyteller.game_session import GameSession


class SaveLoadTests(unittest.TestCase):
    def test_default_save_path_points_into_data_saves(self) -> None:
        default_save_path = get_default_save_path()

        self.assertEqual(default_save_path.parts[-4:], ("adventures", "ADV1", "saves", "current_save.json"))

    def test_save_creates_expected_file_and_load_restores_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir) / "saves" / "current_save.json"
            session = GameSession(save_path=save_path)

            session.process_input("move loc_church")
            save_result = session.process_input("save")

            self.assertTrue(save_path.exists())
            self.assertIn("Game saved to", save_result.output_text)

            session.process_input("move loc_dock")
            load_result = session.process_input("load")

            world = session.get_world_state()
            self.assertEqual(world.player.location_id, "loc_church")
            self.assertEqual(world.current_time, "2026-04-09T22:08:00+02:00")
            self.assertIn("Blackthorn Cafe", load_result.output_text)
            self.assertIn("Saint Judith's Church", load_result.output_text)

    def test_load_without_save_file_fails_gracefully(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir) / "saves" / "current_save.json"
            session = GameSession(save_path=save_path)

            result = session.process_input("load")

            self.assertIn("No save file found", result.output_text)
            self.assertFalse(result.should_quit)

    def test_session_continues_normally_after_load(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir) / "saves" / "current_save.json"
            session = GameSession(save_path=save_path)

            session.process_input("move loc_church")
            session.process_input("save")
            session.process_input("move loc_dock")
            session.process_input("load")
            result = session.process_input("look")

            self.assertIn("Saint Judith's Church", result.output_text)
            self.assertEqual(session.get_world_state().player.location_id, "loc_church")


if __name__ == "__main__":
    unittest.main()
