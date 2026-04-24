from __future__ import annotations

from enum import Enum
import re

from .command_models import DialogueMetadata


class DialogueSubtopic(str, Enum):
    MISSING_LEDGER = "missing_ledger"
    BLOOD_OR_FEEDING_REQUEST = "blood_or_feeding_request"
    FARE_OR_MONEY_SUPPORT = "fare_or_money_support"
    TRANSPORT_OR_VEHICLE_SUPPORT = "transport_or_vehicle_support"
    BACKUP_OR_STAY_NEARBY = "backup_or_stay_nearby"


def detect_dialogue_subtopic(dialogue_metadata: DialogueMetadata | None) -> DialogueSubtopic | None:
    normalized_text = _normalize_dialogue_text(dialogue_metadata)
    if not normalized_text:
        return None
    if _is_blood_or_feeding_request(normalized_text):
        return DialogueSubtopic.BLOOD_OR_FEEDING_REQUEST
    if _is_fare_or_money_support_request(normalized_text):
        return DialogueSubtopic.FARE_OR_MONEY_SUPPORT
    if _is_transport_or_vehicle_support_request(normalized_text):
        return DialogueSubtopic.TRANSPORT_OR_VEHICLE_SUPPORT
    if _is_backup_or_stay_nearby_request(normalized_text):
        return DialogueSubtopic.BACKUP_OR_STAY_NEARBY
    if _is_missing_ledger_topic(normalized_text):
        return DialogueSubtopic.MISSING_LEDGER
    return None


def should_inherit_subtopic(
    active_subtopic: DialogueSubtopic | None,
    dialogue_metadata: DialogueMetadata | None,
) -> bool:
    if active_subtopic is None:
        return False

    normalized_text = _normalize_dialogue_text(dialogue_metadata)
    if not normalized_text:
        return False

    if active_subtopic is DialogueSubtopic.MISSING_LEDGER:
        return _looks_like_missing_ledger_follow_up(normalized_text)
    if active_subtopic is DialogueSubtopic.BLOOD_OR_FEEDING_REQUEST:
        return _looks_like_blood_follow_up(normalized_text)
    if active_subtopic is DialogueSubtopic.FARE_OR_MONEY_SUPPORT:
        return _looks_like_fare_follow_up(normalized_text)
    if active_subtopic is DialogueSubtopic.TRANSPORT_OR_VEHICLE_SUPPORT:
        return _looks_like_transport_follow_up(normalized_text)
    if active_subtopic is DialogueSubtopic.BACKUP_OR_STAY_NEARBY:
        return _looks_like_backup_follow_up(normalized_text)
    return False


def _looks_like_missing_ledger_follow_up(normalized_text: str) -> bool:
    if _is_missing_ledger_topic(normalized_text):
        return True
    if _is_short_please_follow_up(normalized_text):
        return True
    return any(
        phrase in normalized_text
        for phrase in (
            "what about it",
            "what about that",
            "what happened there",
            "what then",
            "and then",
            "tell me more about it",
            "tell me more about that",
            "back to that",
            "go on",
            "continue",
            "carry on",
            "why",
        )
    )


def _looks_like_blood_follow_up(normalized_text: str) -> bool:
    if _is_blood_or_feeding_request(normalized_text):
        return True
    if _is_short_please_follow_up(normalized_text):
        return True
    return any(
        phrase in normalized_text
        for phrase in (
            "why not",
            "eager to please",
            "please a vampire",
            "let me feed",
            "let me feed off",
            "feed off him",
            "feed off you",
            "off him",
            "off you",
            "help a vampire",
            "favor for a vampire",
            "do me this favor",
            "do me a favor",
            "let me",
            "feed",
            "blood",
            "vampire",
        )
    )


def _looks_like_fare_follow_up(normalized_text: str) -> bool:
    return _is_fare_or_money_support_request(normalized_text) or _is_short_please_follow_up(normalized_text)


def _looks_like_transport_follow_up(normalized_text: str) -> bool:
    return _is_transport_or_vehicle_support_request(normalized_text) or _is_short_please_follow_up(normalized_text)


def _looks_like_backup_follow_up(normalized_text: str) -> bool:
    return _is_backup_or_stay_nearby_request(normalized_text) or _is_short_please_follow_up(normalized_text)


def _is_short_please_follow_up(normalized_text: str) -> bool:
    tokens = normalized_text.split()
    return "please" in tokens and len(tokens) <= 4


def _is_blood_or_feeding_request(normalized_text: str) -> bool:
    return any(
        phrase in normalized_text
        for phrase in (
            "need blood",
            "give me blood",
            "get me blood",
            "feed me",
            "feed off him",
            "feed off you",
            "let me feed",
            "let me feed off",
            "letting me feed off him",
            "letting me feed off you",
            "drink from you",
            "drink your blood",
        )
    )


def _is_missing_ledger_topic(normalized_text: str) -> bool:
    if any(
        phrase in normalized_text
        for phrase in (
            "ledger",
            "paper trail",
            "receipt",
            "broker",
            "waterline",
        )
    ):
        return True
    if "dock" not in normalized_text and "docks" not in normalized_text:
        return False
    return any(
        phrase in normalized_text
        for phrase in (
            "what happened",
            "what about",
            "tell me more",
            "where is",
            "back to",
            "what else",
            "what then",
            "why",
        )
    )


def _is_fare_or_money_support_request(normalized_text: str) -> bool:
    if any(
        phrase in normalized_text
        for phrase in (
            "spare change",
            "taxi fare",
            "cab fare",
            "money to pay",
            "money for the taxi",
            "money for the ride",
            "money for the trip",
            "pay for the taxi",
            "pay for the ride",
            "pay for the trip",
            "pay the taxi",
            "pay the fare",
            "cash for the ride",
            "cash for the trip",
            "cover the fare",
        )
    ):
        return True
    has_taxi_context = any(keyword in normalized_text for keyword in ("taxi", "fare", "ride", "trip", "cab"))
    has_money_support_request = any(
        phrase in normalized_text
        for phrase in (
            "spare",
            "change",
            "money",
            "cash",
            "pay",
            "cover",
        )
    )
    return has_taxi_context and has_money_support_request


def _is_transport_or_vehicle_support_request(normalized_text: str) -> bool:
    return any(
        phrase in normalized_text
        for phrase in (
            "do you drive",
            "drive",
            "spare car",
            "have a car",
            "got a car",
            "have some car",
            "ride",
            "lift",
            "drop me off",
            "vehicle",
            "give me a ride",
            "can you drive",
        )
    )


def _is_backup_or_stay_nearby_request(normalized_text: str) -> bool:
    return any(
        phrase in normalized_text
        for phrase in (
            "back me up",
            "backup",
            "back up",
            "watch over me",
            "watch out for me",
            "watch my back",
            "cover me",
            "come along as backup",
            "come along as back up",
            "stay in the car",
            "wait in the car",
            "wait nearby",
            "stay nearby",
            "stay close",
            "wait close",
        )
    )


def _normalize_dialogue_text(dialogue_metadata: DialogueMetadata | None) -> str:
    if dialogue_metadata is None:
        return ""
    return " ".join(
        re.sub(r"[^a-z0-9]+", " ", part.lower()).strip()
        for part in (
            dialogue_metadata.topic or "",
            dialogue_metadata.speech_text or "",
            dialogue_metadata.utterance_text or "",
        )
        if part
    )
