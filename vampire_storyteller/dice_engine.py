from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import random


class DeterministicCheckKind(str, Enum):
    INVESTIGATION = "investigation"
    DIALOGUE_SOCIAL = "dialogue_social"
    GENERIC = "generic"


@dataclass(frozen=True, slots=True)
class DeterministicCheckSpecification:
    kind: DeterministicCheckKind
    seed_parts: tuple[str, ...]
    roll_pool: int
    difficulty: int

    @property
    def seed(self) -> str:
        return "|".join(self.seed_parts)


@dataclass(frozen=True, slots=True)
class DeterministicCheckResolution:
    kind: DeterministicCheckKind
    seed: str
    roll_pool: int
    difficulty: int
    individual_rolls: list[int]
    successes: int
    is_success: bool


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


def resolve_deterministic_check(specification: DeterministicCheckSpecification) -> DeterministicCheckResolution:
    roll_result = roll_dice(specification.roll_pool, specification.difficulty, seed=specification.seed)
    return DeterministicCheckResolution(
        kind=specification.kind,
        seed=specification.seed,
        roll_pool=roll_result.pool,
        difficulty=roll_result.difficulty,
        individual_rolls=list(roll_result.individual_rolls),
        successes=roll_result.successes,
        is_success=roll_result.is_success,
    )
