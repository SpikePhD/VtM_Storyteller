from __future__ import annotations

from enum import Enum
from typing import Any

from .adventure_loader import load_adv1_plot_progression_rules
from .command_models import ConversationStance, DialogueAct, DialogueMetadata
from .world_state import WorldState


class DialogueDomain(str, Enum):
    LEAD_TOPIC = "lead_topic"
    LEAD_PRESSURE = "lead_pressure"
    TRAVEL_PROPOSAL = "travel_proposal"
    OFF_TOPIC_REQUEST = "off_topic_request"
    PROVOCATIVE_OR_INAPPROPRIATE = "provocative_or_inappropriate"
    UNKNOWN_MISC = "unknown_misc"


def classify_dialogue_domain(
    world_state: WorldState,
    npc_id: str,
    dialogue_metadata: DialogueMetadata | None,
    topic_status: Any,
    conversation_stance: ConversationStance = ConversationStance.NEUTRAL,
) -> DialogueDomain:
    combined_text = _normalize_text(_dialogue_metadata_text(dialogue_metadata))
    topic_text = _normalize_text(dialogue_metadata.topic if dialogue_metadata is not None and dialogue_metadata.topic is not None else "")
    dialogue_act = dialogue_metadata.dialogue_act if dialogue_metadata is not None else DialogueAct.UNKNOWN
    plot_rules = load_adv1_plot_progression_rules()

    if npc_id != plot_rules.talk_npc_id:
        return _classify_non_jonas_domain(dialogue_act, topic_status)

    if not combined_text and not topic_text and dialogue_metadata is None:
        return DialogueDomain.LEAD_TOPIC

    if _is_provocative_or_inappropriate(combined_text):
        return DialogueDomain.PROVOCATIVE_OR_INAPPROPRIATE

    if _is_travel_proposal(combined_text):
        return DialogueDomain.TRAVEL_PROPOSAL

    if _is_off_topic_request(combined_text):
        return DialogueDomain.OFF_TOPIC_REQUEST

    if dialogue_act in (DialogueAct.ACCUSE, DialogueAct.THREATEN):
        return DialogueDomain.LEAD_PRESSURE

    if dialogue_act is DialogueAct.PERSUADE and (_is_productive_topic_status(topic_status) or _is_missing_ledger_topic(topic_text or combined_text)):
        return DialogueDomain.LEAD_PRESSURE

    if dialogue_act is DialogueAct.GREET:
        return DialogueDomain.LEAD_TOPIC

    if _is_missing_ledger_topic(topic_text or combined_text):
        return DialogueDomain.LEAD_TOPIC

    if _is_lead_follow_up(world_state, combined_text, conversation_stance):
        return DialogueDomain.LEAD_TOPIC

    if dialogue_act is DialogueAct.ASK:
        return DialogueDomain.LEAD_TOPIC

    if dialogue_act is DialogueAct.UNKNOWN and _is_neutral_conversation_opener(combined_text):
        return DialogueDomain.LEAD_TOPIC

    return DialogueDomain.UNKNOWN_MISC


def _classify_non_jonas_domain(dialogue_act: DialogueAct, topic_status: Any) -> DialogueDomain:
    if dialogue_act is DialogueAct.PERSUADE and _is_productive_topic_status(topic_status):
        return DialogueDomain.LEAD_PRESSURE
    if _is_productive_topic_status(topic_status):
        return DialogueDomain.LEAD_TOPIC
    return DialogueDomain.UNKNOWN_MISC


def _is_lead_follow_up(
    world_state: WorldState,
    combined_text: str,
    conversation_stance: ConversationStance,
) -> bool:
    if not combined_text:
        return False
    if conversation_stance is ConversationStance.GUARDED:
        return False
    if "jonas_shared_dock_lead" not in set(world_state.story_flags):
        return False
    return any(
        phrase in combined_text
        for phrase in (
            "tell me more",
            "please tell me more",
            "go on",
            "what else",
            "say more",
            "continue",
        )
    )


def _is_missing_ledger_topic(normalized_text: str) -> bool:
    if not normalized_text:
        return False
    return any(
        keyword in normalized_text
        for keyword in (
            "dock",
            "docks",
            "ledger",
            "paper trail",
            "receipt",
            "broker",
            "waterline",
        )
    )


def _is_travel_proposal(normalized_text: str) -> bool:
    if not normalized_text:
        return False
    has_travel_verb = any(
        phrase in normalized_text
        for phrase in (
            "come with me",
            "come with us",
            "come with",
            "go with me",
            "go with us",
            "come to the dock",
            "come to the docks",
            "go to the dock",
            "go to the docks",
            "travel with me",
            "travel with us",
        )
    )
    has_location = any(keyword in normalized_text for keyword in ("dock", "docks", "there", "with me", "with us"))
    return has_travel_verb and has_location


def _is_neutral_conversation_opener(normalized_text: str) -> bool:
    if not normalized_text:
        return True
    return any(
        phrase in normalized_text
        for phrase in (
            "we need to speak",
            "need to speak",
            "we should talk",
            "let's talk",
            "speak to",
            "speak with",
            "talk to",
            "talk with",
        )
    ) or normalized_text in {"talk", "speak"}


def _is_off_topic_request(normalized_text: str) -> bool:
    if not normalized_text:
        return False
    return any(
        phrase in normalized_text
        for phrase in (
            "need blood",
            "give me blood",
            "get me blood",
            "feed me",
            "lend me money",
            "give me money",
            "hide me",
        )
    )


def _is_provocative_or_inappropriate(normalized_text: str) -> bool:
    if not normalized_text:
        return False
    return any(
        phrase in normalized_text
        for phrase in (
            "have sex",
            "sleep with me",
            "sleep with us",
            "fuck",
            "kiss me",
            "make out",
        )
    )


def _normalize_text(raw_text: str) -> str:
    return " ".join(raw_text.lower().replace("-", " ").split())


def _is_productive_topic_status(topic_status: Any) -> bool:
    return getattr(topic_status, "value", topic_status) == "productive"


def _dialogue_metadata_text(dialogue_metadata: DialogueMetadata | None) -> str:
    if dialogue_metadata is None:
        return ""

    utterance_text = getattr(dialogue_metadata, "utterance_text", "") or ""
    speech_text = getattr(dialogue_metadata, "speech_text", "") or ""
    topic = getattr(dialogue_metadata, "topic", "") or ""
    return " ".join(part for part in (topic, speech_text, utterance_text) if part)
