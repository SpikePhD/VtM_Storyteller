from __future__ import annotations

from .adventure_loader import load_adv1_world_state
from .world_state import WorldState


def build_sample_world() -> WorldState:
    return load_adv1_world_state()
