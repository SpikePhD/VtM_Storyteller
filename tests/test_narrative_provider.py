from __future__ import annotations

import unittest

from vampire_storyteller.narrative_provider import DeterministicSceneNarrativeProvider
from vampire_storyteller.sample_world import build_sample_world


class NarrativeProviderTests(unittest.TestCase):
    def test_deterministic_provider_renders_scene_text(self) -> None:
        provider = DeterministicSceneNarrativeProvider()
        world = build_sample_world()

        output = provider.render_scene(world)

        self.assertIn("Time: 2026-04-09T22:00:00+02:00", output)
        self.assertIn("NPCs Present: Jonas Reed (Informant, attitude: wary)", output)


if __name__ == "__main__":
    unittest.main()
