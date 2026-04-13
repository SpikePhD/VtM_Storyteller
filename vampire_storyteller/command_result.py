from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CommandResult:
    output_text: str
    should_quit: bool = False
    render_scene: bool = False
    conversation_focus_npc_id: str | None = None
