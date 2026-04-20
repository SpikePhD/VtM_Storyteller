from __future__ import annotations

from dataclasses import dataclass

from .command_models import ConversationStance
from .dialogue_subtopic import DialogueSubtopic
from .world_state import WorldState


@dataclass
class ConversationContext:
    focus_npc_id: str | None = None
    stale_focus_npc_id: str | None = None
    stale_focus_reason: str | None = None
    stance: ConversationStance = ConversationStance.NEUTRAL
    subtopic: DialogueSubtopic | None = None

    def clear(self, reason: str | None = None) -> None:
        if self.focus_npc_id is not None:
            self.stale_focus_npc_id = self.focus_npc_id
            self.stale_focus_reason = reason
        elif reason is not None:
            self.stale_focus_reason = reason
        self.focus_npc_id = None
        self.stance = ConversationStance.NEUTRAL
        self.subtopic = None

    def reset(self) -> None:
        self.focus_npc_id = None
        self.stale_focus_npc_id = None
        self.stale_focus_reason = None
        self.stance = ConversationStance.NEUTRAL
        self.subtopic = None

    def set_focus(
        self,
        npc_id: str,
        stance: ConversationStance = ConversationStance.NEUTRAL,
        subtopic: DialogueSubtopic | None = None,
    ) -> None:
        self.focus_npc_id = npc_id
        self.stale_focus_npc_id = None
        self.stale_focus_reason = None
        self.stance = stance
        self.subtopic = subtopic

    def replace_focus(self, npc_id: str) -> None:
        self.set_focus(npc_id, self.stance, self.subtopic)

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
