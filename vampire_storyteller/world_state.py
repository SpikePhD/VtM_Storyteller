from __future__ import annotations

from dataclasses import dataclass, field

from .models import EventLogEntry, Location, NPC, Player, PlotThread


@dataclass
class WorldState:
    player: Player
    npcs: dict[str, NPC] = field(default_factory=dict)
    locations: dict[str, Location] = field(default_factory=dict)
    plots: dict[str, PlotThread] = field(default_factory=dict)
    current_time: str = ""
    event_log: list[EventLogEntry] = field(default_factory=list)

    def append_event(self, entry: EventLogEntry) -> None:
        self.event_log.append(entry)
