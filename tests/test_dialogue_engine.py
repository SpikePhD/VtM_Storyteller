from __future__ import annotations

import unittest

from vampire_storyteller.command_models import ConversationStance, DialogueAct, DialogueMetadata, TalkCommand
from vampire_storyteller.dialogue_engine import resolve_talk, resolve_talk_result
from vampire_storyteller.plot_engine import advance_plots
from vampire_storyteller.sample_world import build_sample_world


class DialogueEngineTests(unittest.TestCase):
    def test_canonical_talk_without_metadata_still_resolves(self) -> None:
        world = build_sample_world()

        result = resolve_talk(world, "npc_1", None)

        self.assertEqual(result, "")
        self.assertEqual(world.npcs["npc_1"].trust_level, 1)

    def test_greeting_uses_preserved_dialogue_metadata(self) -> None:
        world = build_sample_world()
        metadata = DialogueMetadata(
            utterance_text="Jonas, good evening.",
            speech_text="good evening.",
            dialogue_act=DialogueAct.GREET,
        )

        result = resolve_talk(world, "npc_1", metadata)

        self.assertEqual(result, "")
        self.assertEqual(world.npcs["npc_1"].trust_level, 0)

    def test_aggressive_dialogue_remains_guarded(self) -> None:
        world = build_sample_world()
        threaten_metadata = DialogueMetadata(
            utterance_text="Jonas, talk now or this gets worse.",
            speech_text="talk now or this gets worse.",
            dialogue_act=DialogueAct.THREATEN,
        )

        result = resolve_talk_result(world, "npc_1", threaten_metadata)

        self.assertEqual(result.output_text, "")
        self.assertEqual(result.conversation_stance, ConversationStance.GUARDED)
        self.assertEqual(world.npcs["npc_1"].trust_level, 0)

    def test_question_follow_up_prefers_act_specific_hook_over_generic_trust_hook(self) -> None:
        world = build_sample_world()
        world.npcs["npc_1"].trust_level = 1
        ask_metadata = DialogueMetadata(
            utterance_text="What do you mean?",
            speech_text="What do you mean?",
            dialogue_act=DialogueAct.ASK,
        )

        result = resolve_talk_result(world, "npc_1", ask_metadata)

        self.assertEqual(result.output_text, "")
        self.assertEqual(world.story_flags, [])
        self.assertEqual(world.plots["plot_1"].stage, "hook")

    def test_hostile_follow_up_stays_blocked_and_does_not_emit_story_flag(self) -> None:
        world = build_sample_world()
        world.npcs["npc_1"].trust_level = 1
        hostile_metadata = DialogueMetadata(
            utterance_text="I don't believe you.",
            speech_text="I don't believe you.",
            dialogue_act=DialogueAct.ACCUSE,
        )

        result = resolve_talk_result(world, "npc_1", hostile_metadata)
        plot_messages = advance_plots(world, TalkCommand(npc_id="npc_1", dialogue_metadata=hostile_metadata))

        self.assertEqual(result.output_text, "")
        self.assertEqual(world.story_flags, [])
        self.assertEqual(plot_messages, [])
        self.assertEqual(world.plots["plot_1"].stage, "hook")

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
