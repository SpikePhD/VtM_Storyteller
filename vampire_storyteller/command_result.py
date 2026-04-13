from __future__ import annotations

from dataclasses import dataclass

from .command_models import ConversationStance


@dataclass(frozen=True)
class CommandResult:
    output_text: str
    should_quit: bool = False
    render_scene: bool = False
    conversation_focus_npc_id: str | None = None
    conversation_stance: ConversationStance | None = None
