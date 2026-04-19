from __future__ import annotations

import json
from pathlib import Path

from .world_state import WorldState


def save_world_state(world_state: WorldState, path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(world_state.to_dict(), handle, indent=2, sort_keys=True)


def load_world_state(path: str | Path) -> WorldState:
    source = Path(path)
    with source.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return WorldState.from_dict(data)
