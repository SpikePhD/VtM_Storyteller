from __future__ import annotations

import unittest

from vampire_storyteller.dice_engine import DiceRollResult, roll_dice


class DiceEngineTests(unittest.TestCase):
    def test_roll_dice_is_deterministic_with_seed(self) -> None:
        first = roll_dice(pool=3, difficulty=6, seed="seed-123")
        second = roll_dice(pool=3, difficulty=6, seed="seed-123")

        self.assertIsInstance(first, DiceRollResult)
        self.assertEqual(first, second)

    def test_roll_dice_counts_successes(self) -> None:
        result = roll_dice(pool=3, difficulty=6, seed="seed-123")

        self.assertEqual(result.pool, 3)
        self.assertEqual(result.difficulty, 6)
        self.assertEqual(len(result.individual_rolls), 3)
        self.assertEqual(result.successes, sum(1 for roll in result.individual_rolls if roll >= 6))
        self.assertEqual(result.is_success, result.successes >= 1)

    def test_roll_dice_validates_pool(self) -> None:
        with self.assertRaises(ValueError):
            roll_dice(pool=0, difficulty=6)

    def test_roll_dice_validates_difficulty(self) -> None:
        with self.assertRaises(ValueError):
            roll_dice(pool=1, difficulty=1)
        with self.assertRaises(ValueError):
            roll_dice(pool=1, difficulty=11)


if __name__ == "__main__":
    unittest.main()
