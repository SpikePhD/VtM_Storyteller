from __future__ import annotations

import unittest

from vampire_storyteller.command_models import DialogueAct, DialogueMetadata
from vampire_storyteller.dialogue_engine import resolve_talk
from vampire_storyteller.sample_world import build_sample_world


class DialogueEngineTests(unittest.TestCase):
    def test_canonical_talk_without_metadata_still_resolves(self) -> None:
        world = build_sample_world()

        result = resolve_talk(world, "npc_1", None)

        self.assertIn("Jonas Reed keeps his voice low", result)
        self.assertEqual(world.npcs["npc_1"].trust_level, 1)

    def test_greeting_uses_preserved_dialogue_metadata(self) -> None:
        world = build_sample_world()
        metadata = DialogueMetadata(
            utterance_text="Jonas, good evening.",
            speech_text="good evening.",
            dialogue_act=DialogueAct.GREET,
        )

        result = resolve_talk(world, "npc_1", metadata)

        self.assertIn("gives a brief nod", result)
        self.assertEqual(world.npcs["npc_1"].trust_level, 0)

    def test_aggressive_dialogue_remains_guarded(self) -> None:
        world = build_sample_world()
        threaten_metadata = DialogueMetadata(
            utterance_text="Jonas, talk now or this gets worse.",
            speech_text="talk now or this gets worse.",
            dialogue_act=DialogueAct.THREATEN,
        )

        result = resolve_talk(world, "npc_1", threaten_metadata)

        self.assertIn("ends the exchange", result)
        self.assertEqual(world.npcs["npc_1"].trust_level, 0)

    def test_story_flag_emission_remains_idempotent(self) -> None:
        world = build_sample_world()

        resolve_talk(world, "npc_1", None)
        resolve_talk(world, "npc_1", None)

        self.assertEqual(world.story_flags, ["jonas_shared_dock_lead"])
        self.assertEqual(world.npcs["npc_1"].trust_level, 1)

    def test_absent_npc_feedback_stays_explicit(self) -> None:
        world = build_sample_world()

        result = resolve_talk(world, "npc_2", None)

        self.assertIn("Talk is blocked", result)
        self.assertIn("Sister Eliza", result)

