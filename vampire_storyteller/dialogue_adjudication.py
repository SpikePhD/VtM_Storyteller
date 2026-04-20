from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .command_models import ConversationStance, DialogueAct, DialogueMetadata, TalkCommand
from .adventure_loader import load_adv1_plot_progression_rules
from .dialogue_domain import DialogueDomain, classify_dialogue_domain
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
        )

    metadata = command.dialogue_metadata
    dialogue_act = metadata.dialogue_act if metadata is not None else DialogueAct.UNKNOWN
    topic = metadata.topic if metadata is not None else None
    topic_status = _classify_topic_status(world_state, command.npc_id, dialogue_act, topic, metadata)
    dialogue_domain = classify_dialogue_domain(
        world_state,
        command.npc_id,
        metadata,
        topic_status,
        command.conversation_stance,
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
        )

    if dialogue_act is DialogueAct.PERSUADE and dialogue_domain is DialogueDomain.LEAD_PRESSURE:
        return DialogueAdjudicationOutcome(
            resolution_kind=DialogueAdjudicationResolutionKind.ESCALATED,
            topic_status=topic_status,
            dialogue_domain=dialogue_domain,
            check_required=True,
            reason_code="persuade_check_required",
            explanation=f"{npc.name} can continue the conversation, but persuasion should route to a future social check.",
            conversation_stance=ConversationStance.NEUTRAL,
        )

    if dialogue_act in (DialogueAct.GREET, DialogueAct.ASK):
        return DialogueAdjudicationOutcome(
            resolution_kind=DialogueAdjudicationResolutionKind.ALLOWED,
            topic_status=topic_status,
            dialogue_domain=dialogue_domain,
            check_required=False,
            reason_code=f"{dialogue_act.value}_allowed",
            explanation=f"{npc.name} can continue the conversation normally.",
            conversation_stance=ConversationStance.NEUTRAL,
        )

    if command.conversation_stance is ConversationStance.GUARDED:
        return DialogueAdjudicationOutcome(
            resolution_kind=DialogueAdjudicationResolutionKind.GUARDED,
            topic_status=topic_status,
            dialogue_domain=dialogue_domain,
            check_required=False,
            reason_code="guarded_stance",
            explanation=f"{npc.name} is already in a guarded conversation stance.",
            conversation_stance=ConversationStance.GUARDED,
        )

    return DialogueAdjudicationOutcome(
        resolution_kind=DialogueAdjudicationResolutionKind.ALLOWED,
        topic_status=topic_status,
        dialogue_domain=dialogue_domain,
        check_required=False,
        reason_code="dialogue_fallback_allowed",
        explanation=f"{npc.name} can continue the conversation.",
        conversation_stance=ConversationStance.NEUTRAL,
    )


def _classify_topic_status(
    world_state: WorldState,
    npc_id: str,
    dialogue_act: DialogueAct,
    topic: str | None,
    dialogue_metadata: DialogueMetadata | None = None,
) -> DialogueTopicStatus:
    normalized_topic = _normalize_text(topic or "")
    normalized_dialogue_text = _normalize_text(_dialogue_metadata_text(dialogue_metadata))
    plot_rules = load_adv1_plot_progression_rules()
    plot = world_state.plots.get(plot_rules.plot_id)
    plot_stage = plot.stage if plot is not None else ""
    story_flags = set(world_state.story_flags)
    topic_present = bool(normalized_topic) or bool(normalized_dialogue_text)

    if npc_id != plot_rules.talk_npc_id:
        if dialogue_act in (DialogueAct.ACCUSE, DialogueAct.THREATEN):
            return DialogueTopicStatus.REFUSED
        if dialogue_act is DialogueAct.PERSUADE:
            return DialogueTopicStatus.PRODUCTIVE if _is_missing_ledger_topic(normalized_topic or normalized_dialogue_text) else (DialogueTopicStatus.AVAILABLE if topic_present else DialogueTopicStatus.UNKNOWN)
        return DialogueTopicStatus.AVAILABLE if topic_present else DialogueTopicStatus.UNKNOWN

    if dialogue_act in (DialogueAct.ACCUSE, DialogueAct.THREATEN):
        return DialogueTopicStatus.REFUSED

    if dialogue_act is DialogueAct.GREET:
        return DialogueTopicStatus.AVAILABLE

    if dialogue_act is DialogueAct.PERSUADE:
        if _is_missing_ledger_topic(normalized_topic or normalized_dialogue_text):
            return DialogueTopicStatus.PRODUCTIVE
        return DialogueTopicStatus.AVAILABLE if topic_present else DialogueTopicStatus.UNKNOWN

    if dialogue_act is DialogueAct.ASK:
        if plot_stage in {"hook", "lead_confirmed"} and _is_missing_ledger_topic(normalized_topic or normalized_dialogue_text):
            return DialogueTopicStatus.PRODUCTIVE
        if plot_stage == "hook" and plot_rules.talk_required_story_flag in story_flags:
            return DialogueTopicStatus.PRODUCTIVE if _is_missing_ledger_topic(normalized_topic or normalized_dialogue_text) else DialogueTopicStatus.AVAILABLE
        return DialogueTopicStatus.AVAILABLE if topic_present else DialogueTopicStatus.UNKNOWN

    return DialogueTopicStatus.UNKNOWN if not topic_present else DialogueTopicStatus.AVAILABLE


def _is_missing_ledger_topic(normalized_topic: str) -> bool:
    if not normalized_topic:
        return False
    return any(
        keyword in normalized_topic
        for keyword in (
            "dock",
            "ledger",
            "paper trail",
            "receipt",
            "broker",
        )
    )


def _normalize_text(raw_text: str) -> str:
    return " ".join(raw_text.lower().replace("-", " ").split())


def _dialogue_metadata_text(dialogue_metadata: DialogueMetadata | None) -> str:
    if dialogue_metadata is None:
        return ""

    utterance_text = getattr(dialogue_metadata, "utterance_text", "") or ""
    speech_text = getattr(dialogue_metadata, "speech_text", "") or ""
    topic = getattr(dialogue_metadata, "topic", "") or ""
    return " ".join(part for part in (topic, speech_text, utterance_text) if part)
