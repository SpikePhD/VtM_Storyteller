from __future__ import annotations

import unittest

from vampire_storyteller.command_models import ConversationStance, DialogueAct, DialogueMetadata, TalkCommand
from vampire_storyteller.dialogue_adjudication import (
    DialogueAdjudicationResolutionKind,
    DialogueTopicStatus,
    adjudicate_dialogue_talk,
)
from vampire_storyteller.dialogue_domain import DialogueDomain
from vampire_storyteller.game_session import GameSession
from vampire_storyteller.sample_world import build_sample_world


class DialogueAdjudicationTests(unittest.TestCase):
    def test_greet_and_ask_to_jonas_initial_state_are_allowed(self) -> None:
        world = build_sample_world()
        greet_command = TalkCommand(
            npc_id="npc_1",
            dialogue_metadata=DialogueMetadata(
                utterance_text="Jonas, good evening.",
                speech_text="good evening.",
                dialogue_act=DialogueAct.GREET,
            ),
        )
        ask_command = TalkCommand(
            npc_id="npc_1",
            dialogue_metadata=DialogueMetadata(
                utterance_text="Jonas, what happened at the dock?",
                speech_text="what happened at the dock?",
                dialogue_act=DialogueAct.ASK,
                topic="dock",
            ),
        )

        greet_outcome = adjudicate_dialogue_talk(world, greet_command)
        ask_outcome = adjudicate_dialogue_talk(world, ask_command)

        self.assertTrue(greet_outcome.is_allowed)
        self.assertEqual(greet_outcome.topic_status, DialogueTopicStatus.AVAILABLE)
        self.assertEqual(greet_outcome.dialogue_domain, DialogueDomain.LEAD_TOPIC)
        self.assertTrue(ask_outcome.is_allowed)
        self.assertEqual(ask_outcome.topic_status, DialogueTopicStatus.PRODUCTIVE)
        self.assertEqual(ask_outcome.dialogue_domain, DialogueDomain.LEAD_TOPIC)

    def test_accuse_and_threaten_are_guarded_deterministically(self) -> None:
        world = build_sample_world()
        accuse_command = TalkCommand(
            npc_id="npc_1",
            dialogue_metadata=DialogueMetadata(
                utterance_text="Jonas, you're hiding something.",
                speech_text="you're hiding something.",
                dialogue_act=DialogueAct.ACCUSE,
            ),
        )
        threaten_command = TalkCommand(
            npc_id="npc_1",
            dialogue_metadata=DialogueMetadata(
                utterance_text="Jonas, talk now or this gets worse.",
                speech_text="talk now or this gets worse.",
                dialogue_act=DialogueAct.THREATEN,
            ),
        )

        accuse_outcome = adjudicate_dialogue_talk(world, accuse_command)
        threaten_outcome = adjudicate_dialogue_talk(world, threaten_command)

        self.assertEqual(accuse_outcome.resolution_kind, DialogueAdjudicationResolutionKind.GUARDED)
        self.assertEqual(threaten_outcome.resolution_kind, DialogueAdjudicationResolutionKind.GUARDED)
        self.assertEqual(accuse_outcome.topic_status, DialogueTopicStatus.REFUSED)
        self.assertEqual(threaten_outcome.topic_status, DialogueTopicStatus.REFUSED)
        self.assertEqual(accuse_outcome.dialogue_domain, DialogueDomain.LEAD_PRESSURE)
        self.assertEqual(threaten_outcome.dialogue_domain, DialogueDomain.LEAD_PRESSURE)

    def test_persuade_marks_check_required_without_executing_one(self) -> None:
        world = build_sample_world()
        persuade_command = TalkCommand(
            npc_id="npc_1",
            dialogue_metadata=DialogueMetadata(
                utterance_text="Jonas, help me with the dock.",
                speech_text="help me with the dock.",
                dialogue_act=DialogueAct.PERSUADE,
                topic="dock",
                tone="careful",
            ),
        )

        outcome = adjudicate_dialogue_talk(world, persuade_command)

        self.assertEqual(outcome.resolution_kind, DialogueAdjudicationResolutionKind.ESCALATED)
        self.assertTrue(outcome.check_required)
        self.assertEqual(outcome.topic_status, DialogueTopicStatus.PRODUCTIVE)
        self.assertEqual(outcome.dialogue_domain, DialogueDomain.LEAD_PRESSURE)

    def test_session_records_dialogue_adjudication_on_talk_turn(self) -> None:
        session = GameSession()

        result = session.process_input("Jonas, good evening.")
        turn = session.get_last_action_resolution()

        self.assertIn("Jonas Reed", result.output_text)
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertIsNotNone(turn.dialogue_adjudication)
        assert turn.dialogue_adjudication is not None
        self.assertEqual(turn.dialogue_adjudication.resolution_kind, DialogueAdjudicationResolutionKind.ALLOWED)
        self.assertEqual(turn.dialogue_adjudication.topic_status, DialogueTopicStatus.AVAILABLE)
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.LEAD_TOPIC)
        self.assertEqual(turn.dialogue_adjudication.conversation_stance, ConversationStance.NEUTRAL)


if __name__ == "__main__":
    unittest.main()
