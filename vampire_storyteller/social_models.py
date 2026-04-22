from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .command_models import ConversationStance


def _clamp_social_stat(value: int) -> int:
    return max(0, min(10, value))


class TopicSensitivity(str, Enum):
    OPEN = "open"
    SENSITIVE = "sensitive"
    GUARDED = "guarded"
    BLOCKED = "blocked"


class SocialOutcomeKind(str, Enum):
    REVEAL = "reveal"
    REFUSE = "refuse"
    DEFLECT = "deflect"
    DISENGAGE = "disengage"
    THREATEN = "threaten"
    COOPERATE = "cooperate"


class TopicResult(str, Enum):
    OPENED = "opened"
    BLOCKED = "blocked"
    PARTIAL = "partial"
    UNCHANGED = "unchanged"


class LogisticsCommitment(str, Enum):
    NONE = "none"
    ABSOLUTE_REFUSAL = "absolute_refusal"
    DECLINE_JOIN = "decline_join"
    INDIRECT_SUPPORT = "indirect_support"
    HIDDEN_SUPPORT = "hidden_support"


@dataclass(slots=True)
class NPCSocialState:
    relationship_to_player: str = "unknown"
    trust: int = 0
    hostility: int = 0
    fear: int = 0
    respect: int = 0
    willingness_to_cooperate: int = 0
    current_conversation_stance: ConversationStance = ConversationStance.NEUTRAL
    topic_sensitivity: dict[str, TopicSensitivity] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.trust = _clamp_social_stat(self.trust)
        self.hostility = _clamp_social_stat(self.hostility)
        self.fear = _clamp_social_stat(self.fear)
        self.respect = _clamp_social_stat(self.respect)
        self.willingness_to_cooperate = _clamp_social_stat(self.willingness_to_cooperate)


@dataclass(frozen=True, slots=True)
class SocialStanceShift:
    from_stance: ConversationStance
    to_stance: ConversationStance

    @property
    def changed(self) -> bool:
        return self.from_stance is not self.to_stance


@dataclass(frozen=True, slots=True)
class SocialCheckResult:
    kind: str
    seed: str
    roll_pool: int
    difficulty: int
    successes: int
    is_success: bool


@dataclass(frozen=True, slots=True)
class SocialOutcomePacket:
    outcome_kind: SocialOutcomeKind
    stance_shift: SocialStanceShift
    check_required: bool
    check_result: SocialCheckResult | None
    topic_result: TopicResult
    state_effects: tuple[str, ...]
    plot_effects: tuple[str, ...]
    reason_code: str
    logistics_commitment: LogisticsCommitment = LogisticsCommitment.NONE
