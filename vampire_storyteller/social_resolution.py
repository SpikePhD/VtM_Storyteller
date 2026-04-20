from __future__ import annotations

from dataclasses import dataclass

from .command_models import ConversationStance, DialogueAct
from .dialogue_domain import DialogueDomain
from .social_models import NPCSocialState, SocialOutcomeKind, TopicResult, TopicSensitivity


@dataclass(frozen=True, slots=True)
class SocialResolutionEvaluation:
    topic_key: str
    topic_sensitivity: TopicSensitivity
    openness_score: int
    outcome_kind: SocialOutcomeKind
    topic_result: TopicResult
    check_required: bool
    check_roll_pool: int
    check_difficulty: int
    recommended_stance: ConversationStance
    reason_code: str


def evaluate_topic_openness(
    social_state: NPCSocialState,
    topic: str | None,
    dialogue_act: DialogueAct,
    dialogue_domain: DialogueDomain,
    current_stance: ConversationStance,
) -> SocialResolutionEvaluation:
    topic_key = _normalize_topic(topic)
    topic_sensitivity = _resolve_topic_sensitivity(social_state, topic_key)
    openness_score = _calculate_openness_score(social_state, topic_sensitivity, dialogue_act, dialogue_domain, current_stance)

    if dialogue_act in (DialogueAct.ACCUSE, DialogueAct.THREATEN):
        outcome_kind = SocialOutcomeKind.THREATEN if dialogue_act is DialogueAct.THREATEN else SocialOutcomeKind.REFUSE
        return SocialResolutionEvaluation(
            topic_key=topic_key,
            topic_sensitivity=topic_sensitivity,
            openness_score=openness_score,
            outcome_kind=outcome_kind,
            topic_result=TopicResult.BLOCKED,
            check_required=False,
            check_roll_pool=2,
            check_difficulty=8,
            recommended_stance=ConversationStance.GUARDED,
            reason_code=f"{dialogue_act.value}_blocked",
        )

    if dialogue_act is DialogueAct.GREET:
        return SocialResolutionEvaluation(
            topic_key=topic_key,
            topic_sensitivity=topic_sensitivity,
            openness_score=openness_score,
            outcome_kind=SocialOutcomeKind.COOPERATE,
            topic_result=TopicResult.UNCHANGED,
            check_required=False,
            check_roll_pool=_derive_roll_pool(openness_score),
            check_difficulty=_derive_check_difficulty(openness_score, topic_sensitivity),
            recommended_stance=ConversationStance.NEUTRAL,
            reason_code="greet_cooperative",
        )

    if topic_sensitivity is TopicSensitivity.BLOCKED:
        return SocialResolutionEvaluation(
            topic_key=topic_key,
            topic_sensitivity=topic_sensitivity,
            openness_score=openness_score,
            outcome_kind=SocialOutcomeKind.REFUSE,
            topic_result=TopicResult.BLOCKED,
            check_required=False,
            check_roll_pool=2,
            check_difficulty=8,
            recommended_stance=ConversationStance.GUARDED,
            reason_code="topic_blocked",
        )

    if dialogue_act is DialogueAct.PERSUADE and dialogue_domain in {DialogueDomain.LEAD_TOPIC, DialogueDomain.LEAD_PRESSURE}:
        check_required = openness_score < 7
        if check_required:
            topic_result = TopicResult.PARTIAL if openness_score >= 3 else TopicResult.BLOCKED
            outcome_kind = SocialOutcomeKind.COOPERATE if topic_result is TopicResult.PARTIAL else SocialOutcomeKind.REFUSE
            recommended_stance = ConversationStance.NEUTRAL if topic_result is TopicResult.PARTIAL else ConversationStance.GUARDED
            return SocialResolutionEvaluation(
                topic_key=topic_key,
                topic_sensitivity=topic_sensitivity,
                openness_score=openness_score,
                outcome_kind=outcome_kind,
                topic_result=topic_result,
                check_required=True,
                check_roll_pool=_derive_roll_pool(openness_score),
                check_difficulty=_derive_check_difficulty(openness_score, topic_sensitivity),
                recommended_stance=recommended_stance,
                reason_code="persuade_check_required",
            )
        return SocialResolutionEvaluation(
            topic_key=topic_key,
            topic_sensitivity=topic_sensitivity,
            openness_score=openness_score,
            outcome_kind=SocialOutcomeKind.REVEAL,
            topic_result=TopicResult.OPENED,
            check_required=False,
            check_roll_pool=_derive_roll_pool(openness_score),
            check_difficulty=_derive_check_difficulty(openness_score, topic_sensitivity),
            recommended_stance=ConversationStance.NEUTRAL,
            reason_code="persuade_opened",
        )

    if openness_score >= 6:
        return SocialResolutionEvaluation(
            topic_key=topic_key,
            topic_sensitivity=topic_sensitivity,
            openness_score=openness_score,
            outcome_kind=_positive_outcome_kind(dialogue_domain),
            topic_result=TopicResult.OPENED,
            check_required=False,
            check_roll_pool=_derive_roll_pool(openness_score),
            check_difficulty=_derive_check_difficulty(openness_score, topic_sensitivity),
            recommended_stance=ConversationStance.NEUTRAL,
            reason_code="topic_opened",
        )

    if openness_score >= 3:
        return SocialResolutionEvaluation(
            topic_key=topic_key,
            topic_sensitivity=topic_sensitivity,
            openness_score=openness_score,
            outcome_kind=_deflect_outcome_kind(dialogue_domain),
            topic_result=TopicResult.PARTIAL,
            check_required=False,
            check_roll_pool=_derive_roll_pool(openness_score),
            check_difficulty=_derive_check_difficulty(openness_score, topic_sensitivity),
            recommended_stance=ConversationStance.NEUTRAL,
            reason_code="topic_partial",
        )

    return SocialResolutionEvaluation(
        topic_key=topic_key,
        topic_sensitivity=topic_sensitivity,
        openness_score=openness_score,
        outcome_kind=SocialOutcomeKind.DEFLECT,
        topic_result=TopicResult.BLOCKED,
        check_required=False,
        check_roll_pool=_derive_roll_pool(openness_score),
        check_difficulty=_derive_check_difficulty(openness_score, topic_sensitivity),
        recommended_stance=ConversationStance.GUARDED,
        reason_code="topic_blocked",
    )


def should_require_social_check(evaluation: SocialResolutionEvaluation) -> bool:
    return evaluation.check_required


def _calculate_openness_score(
    social_state: NPCSocialState,
    topic_sensitivity: TopicSensitivity,
    dialogue_act: DialogueAct,
    dialogue_domain: DialogueDomain,
    current_stance: ConversationStance,
) -> int:
    score = (
        social_state.trust
        + social_state.respect
        + social_state.willingness_to_cooperate
        - social_state.hostility
        - social_state.fear
    )
    score += _relationship_modifier(social_state.relationship_to_player)
    score += _sensitivity_modifier(topic_sensitivity)
    score += _stance_modifier(current_stance if current_stance is not ConversationStance.NEUTRAL else social_state.current_conversation_stance)
    score += _dialogue_act_modifier(dialogue_act)
    score += _dialogue_domain_modifier(dialogue_domain)
    return score


def _resolve_topic_sensitivity(social_state: NPCSocialState, topic_key: str) -> TopicSensitivity:
    if topic_key and topic_key in social_state.topic_sensitivity:
        return social_state.topic_sensitivity[topic_key]
    if not topic_key:
        return TopicSensitivity.OPEN
    if any(keyword in topic_key for keyword in ("dock", "ledger", "waterline")):
        return TopicSensitivity.SENSITIVE
    return TopicSensitivity.OPEN


def _normalize_topic(topic: str | None) -> str:
    if topic is None:
        return ""
    return " ".join(topic.lower().replace("-", " ").split())


def _relationship_modifier(relationship: str) -> int:
    normalized = relationship.lower().strip()
    mapping = {
        "ally": 2,
        "friendly": 1,
        "wary": 0,
        "guarded": -1,
        "hostile": -3,
        "unknown": 0,
    }
    return mapping.get(normalized, 0)


def _sensitivity_modifier(sensitivity: TopicSensitivity) -> int:
    return {
        TopicSensitivity.OPEN: 2,
        TopicSensitivity.SENSITIVE: 0,
        TopicSensitivity.GUARDED: -3,
        TopicSensitivity.BLOCKED: -6,
    }[sensitivity]


def _stance_modifier(stance: ConversationStance) -> int:
    return {
        ConversationStance.NEUTRAL: 0,
        ConversationStance.GUARDED: -2,
    }[stance]


def _dialogue_act_modifier(dialogue_act: DialogueAct) -> int:
    return {
        DialogueAct.GREET: 1,
        DialogueAct.ASK: 0,
        DialogueAct.PERSUADE: -2,
        DialogueAct.ACCUSE: -5,
        DialogueAct.THREATEN: -7,
        DialogueAct.UNKNOWN: 0,
    }[dialogue_act]


def _dialogue_domain_modifier(dialogue_domain: DialogueDomain) -> int:
    return {
        DialogueDomain.LEAD_TOPIC: 1,
        DialogueDomain.LEAD_PRESSURE: 0,
        DialogueDomain.TRAVEL_PROPOSAL: -1,
        DialogueDomain.OFF_TOPIC_REQUEST: -2,
        DialogueDomain.PROVOCATIVE_OR_INAPPROPRIATE: -6,
        DialogueDomain.UNKNOWN_MISC: 0,
    }[dialogue_domain]


def _derive_roll_pool(openness_score: int) -> int:
    return 3 if openness_score >= 4 else 2


def _derive_check_difficulty(openness_score: int, topic_sensitivity: TopicSensitivity) -> int:
    difficulty = 8 - min(2, max(0, openness_score // 2))
    if topic_sensitivity is TopicSensitivity.GUARDED:
        difficulty += 1
    if topic_sensitivity is TopicSensitivity.BLOCKED:
        difficulty += 2
    return max(5, min(8, difficulty))


def _positive_outcome_kind(dialogue_domain: DialogueDomain) -> SocialOutcomeKind:
    if dialogue_domain in {DialogueDomain.LEAD_TOPIC, DialogueDomain.LEAD_PRESSURE}:
        return SocialOutcomeKind.REVEAL
    return SocialOutcomeKind.COOPERATE


def _deflect_outcome_kind(dialogue_domain: DialogueDomain) -> SocialOutcomeKind:
    if dialogue_domain in {DialogueDomain.TRAVEL_PROPOSAL, DialogueDomain.OFF_TOPIC_REQUEST, DialogueDomain.UNKNOWN_MISC}:
        return SocialOutcomeKind.DEFLECT
    return SocialOutcomeKind.COOPERATE
