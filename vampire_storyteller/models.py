from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Player:
    id: str
    name: str
    clan: str
    profession: str
    hunger: int
    health: int
    willpower: int
    humanity: int
    inventory: list[str] = field(default_factory=list)
    location_id: str | None = None
    stats: dict[str, int] = field(default_factory=dict)


@dataclass
class NPC:
    id: str
    name: str
    role: str
    location_id: str | None
    attitude_to_player: str
    goals: list[str] = field(default_factory=list)
    schedule: dict[str, str] = field(default_factory=dict)
    traits: dict[str, str] = field(default_factory=dict)


@dataclass
class Location:
    id: str
    name: str
    type: str
    connected_locations: list[str] = field(default_factory=list)
    travel_time: dict[str, int] = field(default_factory=dict)
    danger_level: int = 0


@dataclass
class PlotThread:
    id: str
    name: str
    stage: str
    active: bool
    triggers: list[str] = field(default_factory=list)
    consequences: list[str] = field(default_factory=list)


@dataclass
class EventLogEntry:
    timestamp: str
    description: str
    involved_entities: list[str] = field(default_factory=list)
