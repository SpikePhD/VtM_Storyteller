from __future__ import annotations

from dataclasses import dataclass

from .command_models import ConversationStance
from .world_state import WorldState


@dataclass
class ConversationContext:
    focus_npc_id: str | None = None
    stance: ConversationStance = ConversationStance.NEUTRAL

    def clear(self) -> None:
        self.focus_npc_id = None
        self.stance = ConversationStance.NEUTRAL

    def set_focus(self, npc_id: str, stance: ConversationStance = ConversationStance.NEUTRAL) -> None:
        self.focus_npc_id = npc_id
        self.stance = stance

    def replace_focus(self, npc_id: str) -> None:
        self.set_focus(npc_id)

    def sync_with_world(self, world_state: WorldState) -> None:
        if self.focus_npc_id is None:
            return
        focused_npc = world_state.npcs.get(self.focus_npc_id)
        if focused_npc is None or focused_npc.location_id != world_state.player.location_id:
            self.clear()
