from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .command_models import Command, ConversationStance
from .command_result import CommandResult
from .dice_engine import DiceRollResult
from .input_interpreter import InterpretedInput


class ActionResolutionKind(str, Enum):
    BLOCKED = "blocked"
    AUTOMATIC = "automatic"
    ROLL_GATED = "roll_gated"


class NormalizationSource(str, Enum):
    INTERPRETED = "interpreted"
    DIRECT_COMMAND = "direct_command"
    FAILED = "failed"


class ActionBlockReason(str, Enum):
    INVALID_DESTINATION = "invalid_destination"
    UNSUPPORTED_CONTEXT = "unsupported_context"
    TARGET_NOT_PRESENT = "target_not_present"
    PREREQUISITE_NOT_MET = "prerequisite_not_met"
    TARGET_INACTIVE = "target_inactive"


@dataclass(frozen=True, slots=True)
class AdjudicationDecision:
    resolution_kind: ActionResolutionKind
    reason: str
    blocked_feedback: str | None = None
    block_reason: ActionBlockReason | None = None
    roll_pool: int | None = None
    difficulty: int | None = None

    @property
    def requires_roll(self) -> bool:
        return self.resolution_kind is ActionResolutionKind.ROLL_GATED

    @property
    def is_blocked(self) -> bool:
        return self.resolution_kind is ActionResolutionKind.BLOCKED


@dataclass(frozen=True, slots=True)
class NormalizedActionInput:
    raw_input: str
    command_text: str | None
    command: Command | None
    source: NormalizationSource = NormalizationSource.INTERPRETED
    interpretation: InterpretedInput | None = None
    failure_reason: str | None = None

    @property
    def canonical_command_text(self) -> str | None:
        return self.command_text

    @property
    def is_success(self) -> bool:
        return self.command is not None

    @property
    def used_interpreter(self) -> bool:
        return self.source is NormalizationSource.INTERPRETED

    @property
    def used_parser_boundary(self) -> bool:
        return self.source is NormalizationSource.DIRECT_COMMAND


@dataclass(frozen=True, slots=True)
class ActionAdjudicationOutcome:
    resolution_kind: ActionResolutionKind
    reason: str
    blocked_feedback: str | None = None
    block_reason: ActionBlockReason | None = None
    roll_pool: int | None = None
    difficulty: int | None = None

    @property
    def requires_roll(self) -> bool:
        return self.resolution_kind is ActionResolutionKind.ROLL_GATED

    @property
    def is_blocked(self) -> bool:
        return self.resolution_kind is ActionResolutionKind.BLOCKED

    @property
    def is_check_gated(self) -> bool:
        return self.resolution_kind is ActionResolutionKind.ROLL_GATED

    @classmethod
    def blocked(
        cls,
        reason: str,
        blocked_feedback: str,
        block_reason: ActionBlockReason,
    ) -> "ActionAdjudicationOutcome":
        return cls(
            resolution_kind=ActionResolutionKind.BLOCKED,
            reason=reason,
            blocked_feedback=blocked_feedback,
            block_reason=block_reason,
        )

    @classmethod
    def automatic(cls, reason: str) -> "ActionAdjudicationOutcome":
        return cls(
            resolution_kind=ActionResolutionKind.AUTOMATIC,
            reason=reason,
        )

    @classmethod
    def check_gated(
        cls,
        reason: str,
        roll_pool: int,
        difficulty: int,
    ) -> "ActionAdjudicationOutcome":
        return cls(
            resolution_kind=ActionResolutionKind.ROLL_GATED,
            reason=reason,
            roll_pool=roll_pool,
            difficulty=difficulty,
        )


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
    return ActionAdjudicationOutcome(
        resolution_kind=decision.resolution_kind,
        reason=decision.reason,
        blocked_feedback=decision.blocked_feedback,
        block_reason=decision.block_reason,
        roll_pool=decision.roll_pool,
        difficulty=decision.difficulty,
    )
