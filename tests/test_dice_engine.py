from __future__ import annotations

import unittest

from vampire_storyteller.dice_engine import (
    DeterministicCheckKind,
    DeterministicCheckSpecification,
    DiceRollResult,
    resolve_deterministic_check,
    roll_dice,
)


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

    def test_resolve_deterministic_check_is_reproducible_for_investigation(self) -> None:
        specification = DeterministicCheckSpecification(
            kind=DeterministicCheckKind.INVESTIGATION,
            seed_parts=("2026-04-09T23:23:00+02:00", "investigate", "player_1"),
            roll_pool=3,
            difficulty=4,
        )

        first = resolve_deterministic_check(specification)
        second = resolve_deterministic_check(specification)

        self.assertEqual(first, second)
        self.assertEqual(first.kind, DeterministicCheckKind.INVESTIGATION)
        self.assertEqual(first.seed, "2026-04-09T23:23:00+02:00|investigate|player_1")
        self.assertEqual(first.roll_pool, 3)
        self.assertEqual(first.difficulty, 4)

    def test_resolve_deterministic_check_supports_generic_check_kinds(self) -> None:
        specification = DeterministicCheckSpecification(
            kind=DeterministicCheckKind.GENERIC,
            seed_parts=("scene-probe", "north-dock"),
            roll_pool=2,
            difficulty=6,
        )

        result = resolve_deterministic_check(specification)

        self.assertEqual(result.kind, DeterministicCheckKind.GENERIC)
        self.assertEqual(result.seed, "scene-probe|north-dock")
        self.assertEqual(result.roll_pool, 2)
        self.assertEqual(result.difficulty, 6)
        self.assertEqual(len(result.individual_rolls), 2)


if __name__ == "__main__":
    unittest.main()
