from __future__ import annotations

from typing import Protocol

from .context_builder import build_scene_snapshot, snapshot_to_prompt_text
from .world_state import WorldState


class SceneNarrativeProvider(Protocol):
    def render_scene(self, world_state: WorldState) -> str:
        """Render scene text for the current world state."""


class DeterministicSceneNarrativeProvider:
    def render_scene(self, world_state: WorldState) -> str:
        snapshot = build_scene_snapshot(world_state)
        return snapshot_to_prompt_text(snapshot)
