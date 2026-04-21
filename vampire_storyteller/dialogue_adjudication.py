from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .adventure_loader import load_adv1_dialogue_hook_definitions, load_adv1_dialogue_social_state, load_adv1_plot_progression_rules
from .command_models import ConversationStance, DialogueAct, DialogueMetadata, TalkCommand
from .dialogue_domain import DialogueDomain, classify_dialogue_domain
from .dialogue_subtopic import DialogueSubtopic
from .dialogue_progression_hooks import apply_dialogue_progression_hooks, find_dialogue_hook
from .social_resolution import SocialResolutionEvaluation, evaluate_topic_openness
from .social_models import SocialOutcomeKind, SocialOutcomePacket, SocialStanceShift, TopicResult
from .world_state import WorldState


class DialogueAdjudicationResolutionKind(str, Enum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    GUARDED = "guarded"
    ESCALATED = "escalated"


class DialogueTopicStatus(str, Enum):
    AVAILABLE = "available"
    REFUSED = "refused"
    PRODUCTIVE = "productive"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class DialogueAdjudicationOutcome:
    resolution_kind: DialogueAdjudicationResolutionKind
    topic_status: DialogueTopicStatus
    dialogue_domain: DialogueDomain
    check_required: bool
    reason_code: str
    explanation: str
    blocked_feedback: str | None = None
    conversation_stance: ConversationStance = ConversationStance.NEUTRAL
    social_outcome: SocialOutcomePacket | None = None

    @property
    def is_allowed(self) -> bool:
        return self.resolution_kind is DialogueAdjudicationResolutionKind.ALLOWED

    @property
    def is_blocked(self) -> bool:
        return self.resolution_kind is DialogueAdjudicationResolutionKind.BLOCKED

    @property
    def is_guarded(self) -> bool:
        return self.resolution_kind is DialogueAdjudicationResolutionKind.GUARDED

    @property
    def is_escalated(self) -> bool:
        return self.resolution_kind is DialogueAdjudicationResolutionKind.ESCALATED


def adjudicate_dialogue_talk(world_state: WorldState, command: TalkCommand) -> DialogueAdjudicationOutcome:
    npc = world_state.npcs.get(command.npc_id)
    if npc is None:
        return DialogueAdjudicationOutcome(
            resolution_kind=DialogueAdjudicationResolutionKind.BLOCKED,
            topic_status=DialogueTopicStatus.UNKNOWN,
            dialogue_domain=DialogueDomain.UNKNOWN_MISC,
            check_required=False,
            reason_code="talk_target_missing",
            explanation=f"Talk is blocked: no NPC with id '{command.npc_id}' exists.",
            blocked_feedback=f"Talk is blocked: no NPC with id '{command.npc_id}' exists.",
            social_outcome=_build_social_outcome(
                outcome_kind=SocialOutcomeKind.DISENGAGE,
                previous_stance=command.conversation_stance,
                next_stance=ConversationStance.NEUTRAL,
                check_required=False,
                topic_result=TopicResult.BLOCKED,
                reason_code="talk_target_missing",
            ),
        )

    player_location_id = world_state.player.location_id
    if player_location_id is None:
        return DialogueAdjudicationOutcome(
            resolution_kind=DialogueAdjudicationResolutionKind.BLOCKED,
            topic_status=DialogueTopicStatus.UNKNOWN,
            dialogue_domain=DialogueDomain.UNKNOWN_MISC,
            check_required=False,
            reason_code="talk_location_missing",
            explanation="Talk is blocked: player has no current location.",
            blocked_feedback="Talk is blocked: player has no current location.",
            social_outcome=_build_social_outcome(
                outcome_kind=SocialOutcomeKind.DISENGAGE,
                previous_stance=command.conversation_stance,
                next_stance=ConversationStance.NEUTRAL,
                check_required=False,
                topic_result=TopicResult.BLOCKED,
                reason_code="talk_location_missing",
            ),
        )

    if npc.location_id != player_location_id:
        location = world_state.locations.get(player_location_id)
        location_name = location.name if location is not None else (player_location_id or "unknown location")
        return DialogueAdjudicationOutcome(
            resolution_kind=DialogueAdjudicationResolutionKind.BLOCKED,
            topic_status=DialogueTopicStatus.UNKNOWN,
            dialogue_domain=DialogueDomain.UNKNOWN_MISC,
            check_required=False,
            reason_code="talk_target_absent",
            explanation=f"Talk is blocked: {npc.name} is not present at {location_name}.",
            blocked_feedback=f"Talk is blocked: {npc.name} is not present at {location_name}.",
            social_outcome=_build_social_outcome(
                outcome_kind=SocialOutcomeKind.DISENGAGE,
                previous_stance=command.conversation_stance,
                next_stance=ConversationStance.NEUTRAL,
                check_required=False,
                topic_result=TopicResult.BLOCKED,
                reason_code="talk_target_absent",
            ),
        )

    metadata = command.dialogue_metadata
    dialogue_act = metadata.dialogue_act if metadata is not None else DialogueAct.UNKNOWN
    topic = metadata.topic if metadata is not None else None
    plot_rules = load_adv1_plot_progression_rules()
    plot = world_state.plots.get(plot_rules.plot_id)
    current_stage = plot.stage if plot is not None else ""
    story_flags = set(world_state.story_flags)
    authored_social_state = load_adv1_dialogue_social_state()
    authored_npc_rule = authored_social_state.npc_definitions.get(command.npc_id)
    topic_context = _normalize_text(topic or _topic_context_from_subtopic(command.conversation_subtopic) or _dialogue_metadata_text(metadata))
    dialogue_domain = classify_dialogue_domain(
        world_state,
        command.npc_id,
        metadata,
        DialogueTopicStatus.UNKNOWN,
        command.conversation_stance,
        command.conversation_subtopic,
    )
    evaluation = evaluate_topic_openness(
        npc.social_state,
        topic_context or topic,
        dialogue_act,
        dialogue_domain,
        command.conversation_stance,
        authored_npc_rule=authored_npc_rule,
        plot_id=plot_rules.plot_id,
        plot_stage=current_stage,
        story_flags=story_flags,
    )
    topic_status = _topic_status_from_evaluation(evaluation, dialogue_domain)
    dialogue_domain = classify_dialogue_domain(
        world_state,
        command.npc_id,
        metadata,
        topic_status,
        command.conversation_stance,
        command.conversation_subtopic,
    )
    if topic_status is DialogueTopicStatus.PRODUCTIVE:
        evaluation = evaluate_topic_openness(
            npc.social_state,
            topic_context or topic,
            dialogue_act,
            dialogue_domain,
            command.conversation_stance,
            authored_npc_rule=authored_npc_rule,
            plot_id=plot_rules.plot_id,
            plot_stage=current_stage,
            story_flags=story_flags,
        )
    hooks = load_adv1_dialogue_hook_definitions()
    dialogue_hook = find_dialogue_hook(
        hooks,
        npc,
        current_stage,
        dialogue_act if metadata is not None else None,
        command.conversation_stance,
        plot_rules.plot_id,
    )
    if metadata is None and dialogue_hook is None and dialogue_domain is DialogueDomain.LEAD_TOPIC:
        return DialogueAdjudicationOutcome(
            resolution_kind=DialogueAdjudicationResolutionKind.BLOCKED,
            topic_status=DialogueTopicStatus.UNKNOWN,
            dialogue_domain=dialogue_domain,
            check_required=False,
            reason_code="talk_hook_missing",
            explanation=f"Talk is blocked: {npc.name} has said what he will say for now.",
            blocked_feedback=f"Talk is blocked: {npc.name} has said what he will say for now.",
            conversation_stance=ConversationStance.NEUTRAL,
            social_outcome=_build_social_outcome(
                outcome_kind=SocialOutcomeKind.DISENGAGE,
                previous_stance=command.conversation_stance,
                next_stance=ConversationStance.NEUTRAL,
                check_required=False,
                topic_result=TopicResult.BLOCKED,
                reason_code="talk_hook_missing",
            ),
        )

    if dialogue_domain is DialogueDomain.LEAD_TOPIC:
        apply_dialogue_progression_hooks(
            world_state,
            npc,
            metadata,
            command.conversation_stance,
            dialogue_domain,
        )
    if command.conversation_stance is ConversationStance.GUARDED and not evaluation.check_required and dialogue_act not in (DialogueAct.GREET, DialogueAct.ASK):
        evaluation = SocialResolutionEvaluation(
            topic_key=evaluation.topic_key,
            topic_sensitivity=evaluation.topic_sensitivity,
            openness_score=evaluation.openness_score,
            outcome_kind=evaluation.outcome_kind,
            topic_result=evaluation.topic_result,
            check_required=evaluation.check_required,
            check_roll_pool=evaluation.check_roll_pool,
            check_difficulty=evaluation.check_difficulty,
            recommended_stance=ConversationStance.GUARDED,
            reason_code=evaluation.reason_code,
        )

    if command.conversation_stance is ConversationStance.GUARDED and dialogue_act is DialogueAct.ASK and evaluation.topic_result is TopicResult.OPENED:
        evaluation = SocialResolutionEvaluation(
            topic_key=evaluation.topic_key,
            topic_sensitivity=evaluation.topic_sensitivity,
            openness_score=evaluation.openness_score,
            outcome_kind=SocialOutcomeKind.DEFLECT,
            topic_result=TopicResult.PARTIAL,
            check_required=False,
            check_roll_pool=evaluation.check_roll_pool,
            check_difficulty=evaluation.check_difficulty,
            recommended_stance=ConversationStance.GUARDED,
            reason_code="guarded_ask_partial",
        )

    if dialogue_act in (DialogueAct.ACCUSE, DialogueAct.THREATEN):
        return DialogueAdjudicationOutcome(
            resolution_kind=DialogueAdjudicationResolutionKind.GUARDED,
            topic_status=DialogueTopicStatus.REFUSED,
            dialogue_domain=dialogue_domain,
            check_required=False,
            reason_code=f"{dialogue_act.value}_guarded",
            explanation=f"{npc.name} stays guarded in response to the {dialogue_act.value}.",
            conversation_stance=ConversationStance.GUARDED,
            social_outcome=_build_social_outcome(
                outcome_kind=evaluation.outcome_kind,
                previous_stance=command.conversation_stance,
                next_stance=ConversationStance.GUARDED,
                check_required=False,
                topic_result=TopicResult.BLOCKED,
                reason_code=f"{dialogue_act.value}_guarded",
            ),
        )

    if evaluation.check_required and dialogue_act is DialogueAct.PERSUADE:
        return DialogueAdjudicationOutcome(
            resolution_kind=DialogueAdjudicationResolutionKind.ESCALATED,
            topic_status=topic_status,
            dialogue_domain=dialogue_domain,
            check_required=True,
            reason_code="persuade_check_required",
            explanation=(
                f"{npc.name} can continue the conversation, but the current social state says persuasion should route to a future social check."
            ),
            conversation_stance=evaluation.recommended_stance,
            social_outcome=_build_social_outcome(
                outcome_kind=evaluation.outcome_kind,
                previous_stance=command.conversation_stance,
                next_stance=evaluation.recommended_stance,
                check_required=True,
                topic_result=evaluation.topic_result,
                reason_code="persuade_check_required",
            ),
        )

    if evaluation.topic_result is TopicResult.BLOCKED or command.conversation_stance is ConversationStance.GUARDED or evaluation.recommended_stance is ConversationStance.GUARDED:
        return DialogueAdjudicationOutcome(
            resolution_kind=DialogueAdjudicationResolutionKind.GUARDED,
            topic_status=topic_status,
            dialogue_domain=dialogue_domain,
            check_required=False,
            reason_code="guarded_stance",
            explanation=f"{npc.name} is already in a guarded conversation stance.",
            conversation_stance=ConversationStance.GUARDED,
            social_outcome=_build_social_outcome(
                outcome_kind=evaluation.outcome_kind,
                previous_stance=command.conversation_stance,
                next_stance=ConversationStance.GUARDED,
                check_required=False,
                topic_result=evaluation.topic_result,
                reason_code="guarded_stance",
            ),
        )

    if dialogue_act in (DialogueAct.GREET, DialogueAct.ASK):
        return DialogueAdjudicationOutcome(
            resolution_kind=DialogueAdjudicationResolutionKind.ALLOWED,
            topic_status=topic_status,
            dialogue_domain=dialogue_domain,
            check_required=False,
            reason_code=f"{dialogue_act.value}_allowed",
            explanation=f"{npc.name} can continue the conversation normally.",
            conversation_stance=evaluation.recommended_stance,
            social_outcome=_build_social_outcome(
                outcome_kind=evaluation.outcome_kind,
                previous_stance=command.conversation_stance,
                next_stance=evaluation.recommended_stance,
                check_required=False,
                topic_result=evaluation.topic_result,
                reason_code=f"{dialogue_act.value}_allowed",
            ),
        )

    return DialogueAdjudicationOutcome(
        resolution_kind=DialogueAdjudicationResolutionKind.ALLOWED,
        topic_status=topic_status,
        dialogue_domain=dialogue_domain,
        check_required=False,
        reason_code="dialogue_fallback_allowed",
        explanation=f"{npc.name} can continue the conversation.",
        conversation_stance=evaluation.recommended_stance,
        social_outcome=_build_social_outcome(
            outcome_kind=evaluation.outcome_kind,
            previous_stance=command.conversation_stance,
            next_stance=evaluation.recommended_stance,
            check_required=False,
            topic_result=evaluation.topic_result,
            reason_code="dialogue_fallback_allowed",
        ),
    )


def _build_social_outcome(
    *,
    outcome_kind: SocialOutcomeKind,
    previous_stance: ConversationStance,
    next_stance: ConversationStance,
    check_required: bool,
    topic_result: TopicResult,
    reason_code: str,
) -> SocialOutcomePacket:
    return SocialOutcomePacket(
        outcome_kind=outcome_kind,
        stance_shift=SocialStanceShift(from_stance=previous_stance, to_stance=next_stance),
        check_required=check_required,
        check_result=None,
        topic_result=topic_result,
        state_effects=(),
        plot_effects=(),
        reason_code=reason_code,
    )


def _topic_status_from_evaluation(
    evaluation: SocialResolutionEvaluation,
    dialogue_domain: DialogueDomain,
) -> DialogueTopicStatus:
    if evaluation.topic_result is TopicResult.OPENED:
        return DialogueTopicStatus.PRODUCTIVE
    if dialogue_domain in {DialogueDomain.LEAD_TOPIC, DialogueDomain.LEAD_PRESSURE} and evaluation.topic_result is TopicResult.PARTIAL:
        return DialogueTopicStatus.PRODUCTIVE
    if evaluation.topic_result in {TopicResult.PARTIAL, TopicResult.UNCHANGED}:
        return DialogueTopicStatus.AVAILABLE
    if evaluation.topic_result is TopicResult.BLOCKED:
        return DialogueTopicStatus.REFUSED
    return DialogueTopicStatus.UNKNOWN


def _normalize_text(raw_text: str) -> str:
    return " ".join(raw_text.lower().replace("-", " ").split())


def _dialogue_metadata_text(dialogue_metadata: DialogueMetadata | None) -> str:
    if dialogue_metadata is None:
        return ""

    utterance_text = getattr(dialogue_metadata, "utterance_text", "") or ""
    speech_text = getattr(dialogue_metadata, "speech_text", "") or ""
    topic = getattr(dialogue_metadata, "topic", "") or ""
    return " ".join(part for part in (topic, speech_text, utterance_text) if part)


def _topic_context_from_subtopic(active_subtopic: DialogueSubtopic | None) -> str | None:
    if active_subtopic is DialogueSubtopic.MISSING_LEDGER:
        return "dock"
    return None
