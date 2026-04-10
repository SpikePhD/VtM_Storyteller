from __future__ import annotations

from dataclasses import dataclass
import random


@dataclass(frozen=True, slots=True)
class DiceRollResult:
    pool: int
    difficulty: int
    individual_rolls: list[int]
    successes: int
    is_success: bool


def roll_dice(pool: int, difficulty: int, seed: str | None = None) -> DiceRollResult:
    if pool < 1:
        raise ValueError("pool must be >= 1")
    if difficulty < 2 or difficulty > 10:
        raise ValueError("difficulty must be between 2 and 10 inclusive")

    rng = random.Random(seed)
    individual_rolls = [rng.randint(1, 10) for _ in range(pool)]
    successes = sum(1 for roll in individual_rolls if roll >= difficulty)
    return DiceRollResult(
        pool=pool,
        difficulty=difficulty,
        individual_rolls=individual_rolls,
        successes=successes,
        is_success=successes >= 1,
    )
