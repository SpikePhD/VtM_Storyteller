from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SceneNPC:
    id: str
    name: str
    role: str
    attitude_to_player: str


@dataclass
class SceneSnapshot:
    timestamp: str
    player_name: str
    player_clan: str
    player_hunger: int
    player_health: int
    player_willpower: int
    player_humanity: int
    location_id: str
    location_name: str
    location_type: str
    location_danger_level: int
    exits: list[str] = field(default_factory=list)
    npcs_present: list[SceneNPC] = field(default_factory=list)
    active_plots: list[str] = field(default_factory=list)
    recent_events: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class SceneNarrationPayload:
    timestamp: str
    player_name: str
    player_clan: str
    location_name: str
    exits: list[str] = field(default_factory=list)
    npcs_present: list[SceneNPC] = field(default_factory=list)
    active_plots: list[str] = field(default_factory=list)
    recent_events: list[str] = field(default_factory=list)
