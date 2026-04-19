from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .adjudication_engine import AdjudicationDecision
from .command_models import Command, ConversationStance
from .command_result import CommandResult
from .dice_engine import DiceRollResult
from .input_interpreter import InterpretedInput


class ActionResolutionKind(str, Enum):
    BLOCKED = "blocked"
    AUTOMATIC = "automatic"
    ROLL_GATED = "roll_gated"


@dataclass(frozen=True, slots=True)
class NormalizedActionInput:
    raw_input: str
    command_text: str
    command: Command
    interpretation: InterpretedInput | None = None


@dataclass(frozen=True, slots=True)
class ActionAdjudicationOutcome:
    resolution_kind: ActionResolutionKind
    reason: str
    blocked_feedback: str | None = None
    roll_pool: int | None = None
    difficulty: int | None = None

    @property
    def requires_roll(self) -> bool:
        return self.resolution_kind is ActionResolutionKind.ROLL_GATED


@dataclass(frozen=True, slots=True)
class ActionCheckOutcome:
    seed: str
    roll_pool: int
    difficulty: int
    individual_rolls: list[int]
    successes: int
    is_success: bool

    @classmethod
    def from_roll_result(cls, seed: str, roll_result: DiceRollResult) -> "ActionCheckOutcome":
        return cls(
            seed=seed,
            roll_pool=roll_result.pool,
            difficulty=roll_result.difficulty,
            individual_rolls=list(roll_result.individual_rolls),
            successes=roll_result.successes,
            is_success=roll_result.is_success,
        )


@dataclass(frozen=True, slots=True)
class ActionConsequenceSummary:
    messages: tuple[str, ...] = ()

    @property
    def has_messages(self) -> bool:
        return bool(self.messages)


@dataclass(frozen=True, slots=True)
class ActionResolutionTurn:
    normalized_action: NormalizedActionInput
    adjudication: ActionAdjudicationOutcome
    check: ActionCheckOutcome | None
    consequence_summary: ActionConsequenceSummary
    output_text: str
    should_quit: bool
    render_scene: bool
    conversation_focus_npc_id: str | None
    conversation_stance: ConversationStance | None

    def to_command_result(self) -> CommandResult:
        return CommandResult(
            output_text=self.output_text,
            should_quit=self.should_quit,
            render_scene=self.render_scene,
            conversation_focus_npc_id=self.conversation_focus_npc_id,
            conversation_stance=self.conversation_stance,
        )


def adjudication_outcome_from_decision(decision: AdjudicationDecision) -> ActionAdjudicationOutcome:
    if decision.requires_roll:
        resolution_kind = ActionResolutionKind.ROLL_GATED
    elif decision.blocked_feedback is not None:
        resolution_kind = ActionResolutionKind.BLOCKED
    else:
        resolution_kind = ActionResolutionKind.AUTOMATIC

    return ActionAdjudicationOutcome(
        resolution_kind=resolution_kind,
        reason=decision.reason,
        blocked_feedback=decision.blocked_feedback,
        roll_pool=decision.roll_pool,
        difficulty=decision.difficulty,
    )
