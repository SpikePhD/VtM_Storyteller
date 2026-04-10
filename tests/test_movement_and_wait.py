from __future__ import annotations

import unittest

from vampire_storyteller.actions import wait_action
from vampire_storyteller.exceptions import InvalidLocationError, MovementError
from vampire_storyteller.map_engine import move_player
from vampire_storyteller.sample_world import build_sample_world


class MovementAndWaitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = build_sample_world()

    def test_successful_move_updates_location(self) -> None:
        move_player(self.world, "loc_church")
        self.assertEqual(self.world.player.location_id, "loc_church")

    def test_sample_world_uses_file_backed_map_graph(self) -> None:
        self.assertEqual(self.world.locations["loc_cafe"].connected_locations, ["loc_church", "loc_dock"])
        self.assertEqual(self.world.locations["loc_church"].travel_time["loc_dock"], 15)

    def test_successful_move_advances_time(self) -> None:
        move_player(self.world, "loc_church")
        self.assertEqual(self.world.current_time, "2026-04-09T22:08:00+02:00")

    def test_invalid_move_raises_expected_exception(self) -> None:
        with self.assertRaises(InvalidLocationError):
            move_player(self.world, "loc_missing")

    def test_wait_advances_time(self) -> None:
        wait_action(self.world, 30)
        self.assertEqual(self.world.current_time, "2026-04-09T22:30:00+02:00")

    def test_wait_under_sixty_minutes_does_not_increase_hunger(self) -> None:
        wait_action(self.world, 59)
        self.assertEqual(self.world.player.hunger, 2)

    def test_wait_sixty_minutes_increases_hunger(self) -> None:
        wait_action(self.world, 60)
        self.assertEqual(self.world.player.hunger, 3)

    def test_hunger_does_not_exceed_cap(self) -> None:
        self.world.player.hunger = 4
        wait_action(self.world, 120)
        self.assertEqual(self.world.player.hunger, 5)


if __name__ == "__main__":
    unittest.main()
