from __future__ import annotations

from dataclasses import dataclass, field

from .models import EventLogEntry, Location, NPC, Player, PlotThread


@dataclass
class WorldState:
    player: Player
    npcs: dict[str, NPC] = field(default_factory=dict)
    locations: dict[str, Location] = field(default_factory=dict)
    plots: dict[str, PlotThread] = field(default_factory=dict)
    story_flags: list[str] = field(default_factory=list)
    current_time: str = ""
    event_log: list[EventLogEntry] = field(default_factory=list)

    def append_event(self, entry: EventLogEntry) -> None:
        self.event_log.append(entry)

    def add_story_flag(self, story_flag: str) -> bool:
        if story_flag in self.story_flags:
            return False
        self.story_flags.append(story_flag)
        return True
