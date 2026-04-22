from __future__ import annotations

from dataclasses import dataclass, field

from .command_models import ConversationStance
from .dialogue_subtopic import DialogueSubtopic
from .world_state import WorldState


MAX_RECENT_DIALOGUE_ENTRIES = 12


@dataclass(frozen=True, slots=True)
class DialogueHistoryEntry:
    speaker: str
    utterance_text: str


@dataclass(frozen=True, slots=True)
class DialogueMemoryContext:
    previous_interactions_summary: str = ""
    recent_dialogue_history: tuple[DialogueHistoryEntry, ...] = ()


@dataclass
class ConversationContext:
    focus_npc_id: str | None = None
    stale_focus_npc_id: str | None = None
    stale_focus_reason: str | None = None
    stance: ConversationStance = ConversationStance.NEUTRAL
    active_dialogue_subtopic: DialogueSubtopic | None = None
    recent_dialogue_history: tuple[DialogueHistoryEntry, ...] = field(default_factory=tuple)

    @property
    def subtopic(self) -> DialogueSubtopic | None:
        return self.active_dialogue_subtopic

    @subtopic.setter
    def subtopic(self, value: DialogueSubtopic | None) -> None:
        self.active_dialogue_subtopic = value

    def clear(self, reason: str | None = None) -> None:
        if self.focus_npc_id is not None:
            self.stale_focus_npc_id = self.focus_npc_id
            self.stale_focus_reason = reason
        elif reason is not None:
            self.stale_focus_reason = reason
        self.focus_npc_id = None
        self.stance = ConversationStance.NEUTRAL
        self.active_dialogue_subtopic = None
        self.recent_dialogue_history = ()

    def reset(self) -> None:
        self.focus_npc_id = None
        self.stale_focus_npc_id = None
        self.stale_focus_reason = None
        self.stance = ConversationStance.NEUTRAL
        self.active_dialogue_subtopic = None
        self.recent_dialogue_history = ()

    def clear_subtopic(self) -> None:
        self.active_dialogue_subtopic = None

    def set_focus(
        self,
        npc_id: str,
        stance: ConversationStance = ConversationStance.NEUTRAL,
        subtopic: DialogueSubtopic | None = None,
    ) -> None:
        if self.focus_npc_id != npc_id:
            self.recent_dialogue_history = ()
        self.focus_npc_id = npc_id
        self.stale_focus_npc_id = None
        self.stale_focus_reason = None
        self.stance = stance
        self.active_dialogue_subtopic = subtopic

    def replace_focus(self, npc_id: str) -> None:
        self.set_focus(npc_id, self.stance, self.active_dialogue_subtopic)

    def record_dialogue_utterance(self, speaker: str, utterance_text: str) -> None:
        speaker_text = speaker.strip()
        utterance = " ".join(utterance_text.strip().split())
        if not speaker_text or not utterance:
            return
        history = self.recent_dialogue_history + (
            DialogueHistoryEntry(speaker=speaker_text, utterance_text=utterance),
        )
        if len(history) > MAX_RECENT_DIALOGUE_ENTRIES:
            history = history[-MAX_RECENT_DIALOGUE_ENTRIES:]
        self.recent_dialogue_history = history

    def build_memory_context(self, previous_interactions_summary: str = "") -> DialogueMemoryContext:
        return DialogueMemoryContext(
            previous_interactions_summary=" ".join(previous_interactions_summary.strip().split()),
            recent_dialogue_history=self.recent_dialogue_history,
        )

    def sync_with_world(self, world_state: WorldState) -> None:
        if self.focus_npc_id is None:
            return
        focused_npc = world_state.npcs.get(self.focus_npc_id)
        if focused_npc is None:
            self.clear("Talk is blocked: the previous conversation target is no longer available.")
            return

        if focused_npc.location_id != world_state.player.location_id:
            location = world_state.locations.get(world_state.player.location_id or "")
            location_name = location.name if location is not None else (world_state.player.location_id or "unknown location")
            self.clear(
                f"Talk is blocked: {focused_npc.name} is not present at {location_name}, so that conversation cannot continue."
            )
