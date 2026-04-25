from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DialogueFactCard:
    fact_id: str
    kind: str
    summary: str
    npc_id: str | None = None
    plot_id: str | None = None
    reveal_plot_stage: str | None = None
    reveal_story_flags: tuple[str, ...] = ()
    reveal_trust_level: int | None = None
