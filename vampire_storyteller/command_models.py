from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DialogueAct(str, Enum):
    GREET = "greet"
    ASK = "ask"
    ACCUSE = "accuse"
    PERSUADE = "persuade"
    THREATEN = "threaten"
    UNKNOWN = "unknown"


class ConversationStance(str, Enum):
    NEUTRAL = "neutral"
    GUARDED = "guarded"


@dataclass(frozen=True, slots=True)
class DialogueMetadata:
    utterance_text: str
    speech_text: str
    dialogue_act: DialogueAct
    topic: str | None = None
    tone: str | None = None


@dataclass(frozen=True)
class Command:
    """Base type for parsed structured commands."""


@dataclass(frozen=True)
class LookCommand(Command):
    pass


@dataclass(frozen=True)
class StatusCommand(Command):
    pass


@dataclass(frozen=True)
class HelpCommand(Command):
    pass


@dataclass(frozen=True)
class MoveCommand(Command):
    destination_id: str


@dataclass(frozen=True)
class WaitCommand(Command):
    minutes: int


@dataclass(frozen=True)
class TalkCommand(Command):
    npc_id: str
    dialogue_metadata: DialogueMetadata | None = None
    conversation_stance: ConversationStance = ConversationStance.NEUTRAL


@dataclass(frozen=True)
class InvestigateCommand(Command):
    pass


@dataclass(frozen=True)
class SaveCommand(Command):
    pass


@dataclass(frozen=True)
class LoadCommand(Command):
    pass


@dataclass(frozen=True)
class QuitCommand(Command):
    pass
