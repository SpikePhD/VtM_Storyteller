from __future__ import annotations

import unittest

from vampire_storyteller.command_models import ConversationStance, DialogueAct, DialogueMetadata, TalkCommand
from vampire_storyteller.dialogue_adjudication import (
    DialogueAdjudicationResolutionKind,
    DialogueTopicStatus,
    adjudicate_dialogue_talk,
)
from vampire_storyteller.dialogue_domain import DialogueDomain
from vampire_storyteller.dialogue_subtopic import DialogueSubtopic
from vampire_storyteller.game_session import GameSession
from vampire_storyteller.sample_world import build_sample_world
from vampire_storyteller.social_models import LogisticsCommitment, SocialOutcomeKind, TopicResult, TopicSensitivity


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
        self.assertEqual(greet_outcome.social_outcome.outcome_kind, SocialOutcomeKind.COOPERATE)
        self.assertEqual(greet_outcome.social_outcome.topic_result, TopicResult.UNCHANGED)
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
        self.assertIsNotNone(outcome.social_outcome)
        assert outcome.social_outcome is not None
        self.assertEqual(outcome.social_outcome.outcome_kind, SocialOutcomeKind.COOPERATE)
        self.assertEqual(outcome.social_outcome.topic_result, TopicResult.PARTIAL)
        self.assertTrue(outcome.social_outcome.check_required)

    def test_taxi_money_support_request_stays_off_topic_even_with_dock_reference(self) -> None:
        world = build_sample_world()
        command = TalkCommand(
            npc_id="npc_1",
            dialogue_metadata=DialogueMetadata(
                utterance_text="Jonas I don't have money to pay for the taxi to the dock!",
                speech_text="I don't have money to pay for the taxi to the dock!",
                dialogue_act=DialogueAct.UNKNOWN,
                topic="dock",
            ),
        )

        outcome = adjudicate_dialogue_talk(world, command)

        self.assertEqual(outcome.dialogue_domain, DialogueDomain.OFF_TOPIC_REQUEST)
        self.assertEqual(outcome.topic_status, DialogueTopicStatus.AVAILABLE)
        self.assertTrue(outcome.is_allowed)
        self.assertFalse(outcome.check_required)
        self.assertIsNotNone(outcome.social_outcome)
        assert outcome.social_outcome is not None
        self.assertEqual(outcome.social_outcome.outcome_kind, SocialOutcomeKind.DEFLECT)
        self.assertEqual(outcome.social_outcome.topic_result, TopicResult.PARTIAL)

    def test_topic_sensitivity_changes_adjudication_openness(self) -> None:
        world = build_sample_world()
        world.npcs["npc_1"].social_state.topic_sensitivity["dock"] = TopicSensitivity.BLOCKED
        command = TalkCommand(
            npc_id="npc_1",
            dialogue_metadata=DialogueMetadata(
                utterance_text="Jonas, what happened at the dock?",
                speech_text="what happened at the dock?",
                dialogue_act=DialogueAct.ASK,
                topic="dock",
            ),
        )

        outcome = adjudicate_dialogue_talk(world, command)

        self.assertEqual(outcome.resolution_kind, DialogueAdjudicationResolutionKind.GUARDED)
        self.assertEqual(outcome.topic_status, DialogueTopicStatus.REFUSED)
        self.assertEqual(outcome.social_outcome.topic_result, TopicResult.BLOCKED)
        self.assertEqual(outcome.social_outcome.outcome_kind, SocialOutcomeKind.REFUSE)

    def test_higher_trust_and_willingness_reduce_persuasion_pressure(self) -> None:
        world = build_sample_world()
        npc = world.npcs["npc_1"]
        npc.social_state.trust = 8
        npc.social_state.willingness_to_cooperate = 8
        npc.social_state.respect = 8
        npc.social_state.hostility = 0
        npc.social_state.fear = 0
        npc.trust_level = npc.social_state.trust

        command = TalkCommand(
            npc_id="npc_1",
            dialogue_metadata=DialogueMetadata(
                utterance_text="Jonas, help me with the dock.",
                speech_text="help me with the dock.",
                dialogue_act=DialogueAct.PERSUADE,
                topic="dock",
                tone="careful",
            ),
        )

        outcome = adjudicate_dialogue_talk(world, command)

        self.assertTrue(outcome.is_allowed)
        self.assertEqual(outcome.topic_status, DialogueTopicStatus.PRODUCTIVE)
        self.assertFalse(outcome.check_required)
        self.assertIsNotNone(outcome.social_outcome)
        assert outcome.social_outcome is not None
        self.assertEqual(outcome.social_outcome.topic_result, TopicResult.OPENED)
        self.assertEqual(outcome.social_outcome.outcome_kind, SocialOutcomeKind.REVEAL)

    def test_missing_ledger_subtopic_keeps_follow_up_in_lead_lane(self) -> None:
        world = build_sample_world()
        command = TalkCommand(
            npc_id="npc_1",
            conversation_subtopic=DialogueSubtopic.MISSING_LEDGER,
            dialogue_metadata=DialogueMetadata(
                utterance_text="What about it",
                speech_text="what about it",
                dialogue_act=DialogueAct.ASK,
            ),
        )

        outcome = adjudicate_dialogue_talk(world, command)

        self.assertTrue(outcome.is_allowed)
        self.assertEqual(outcome.dialogue_domain, DialogueDomain.LEAD_TOPIC)
        self.assertEqual(outcome.topic_status, DialogueTopicStatus.PRODUCTIVE)
        self.assertIsNotNone(outcome.social_outcome)

    def test_vague_discourse_marker_does_not_inherit_missing_ledger_subtopic(self) -> None:
        world = build_sample_world()
        command = TalkCommand(
            npc_id="npc_1",
            conversation_subtopic=DialogueSubtopic.MISSING_LEDGER,
            dialogue_metadata=DialogueMetadata(
                utterance_text="See what I mean?",
                speech_text="see what I mean?",
                dialogue_act=DialogueAct.ASK,
                topic="conversation",
            ),
        )

        outcome = adjudicate_dialogue_talk(world, command)

        self.assertTrue(outcome.is_allowed)
        self.assertEqual(outcome.dialogue_domain, DialogueDomain.META_CONVERSATION)
        self.assertIsNotNone(outcome.social_outcome)
        assert outcome.social_outcome is not None
        self.assertNotEqual(outcome.social_outcome.topic_result, TopicResult.OPENED)
        self.assertNotEqual(outcome.social_outcome.outcome_kind, SocialOutcomeKind.REVEAL)

    def test_missing_ledger_subtopic_does_not_make_threats_productive(self) -> None:
        world = build_sample_world()
        command = TalkCommand(
            npc_id="npc_1",
            conversation_subtopic=DialogueSubtopic.MISSING_LEDGER,
            dialogue_metadata=DialogueMetadata(
                utterance_text="Jonas, talk now or this gets worse.",
                speech_text="talk now or this gets worse.",
                dialogue_act=DialogueAct.THREATEN,
            ),
        )

        outcome = adjudicate_dialogue_talk(world, command)

        self.assertEqual(outcome.resolution_kind, DialogueAdjudicationResolutionKind.GUARDED)
        self.assertEqual(outcome.topic_status, DialogueTopicStatus.REFUSED)
        self.assertEqual(outcome.dialogue_domain, DialogueDomain.LEAD_PRESSURE)

    def test_session_records_dialogue_adjudication_on_talk_turn(self) -> None:
        session = GameSession()

        session.process_input("/talk with Jonas")
        result = session.process_input("good evening.")
        turn = session.get_last_action_resolution()

        self.assertTrue(result.output_text.strip())
        self.assertNotIn("paper trail", result.output_text.lower())
        self.assertIsNotNone(result.dialogue_presentation)
        assert result.dialogue_presentation is not None
        self.assertEqual(result.dialogue_presentation.npc_display_name, "Jonas Reed")
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertIsNotNone(turn.dialogue_adjudication)
        assert turn.dialogue_adjudication is not None
        self.assertEqual(turn.dialogue_adjudication.resolution_kind, DialogueAdjudicationResolutionKind.ALLOWED)
        self.assertEqual(turn.dialogue_adjudication.topic_status, DialogueTopicStatus.AVAILABLE)
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.LEAD_TOPIC)
        self.assertEqual(turn.dialogue_adjudication.conversation_stance, ConversationStance.NEUTRAL)
        self.assertIsNotNone(turn.social_outcome)
        assert turn.social_outcome is not None
        self.assertEqual(turn.social_outcome.outcome_kind, SocialOutcomeKind.COOPERATE)
        self.assertEqual(turn.social_outcome.topic_result, TopicResult.UNCHANGED)

    def test_travel_request_turn_records_bounded_logistics_commitment(self) -> None:
        session = GameSession()

        session.process_input("/talk with Jonas")
        result = session.process_input("Are you coming with?")
        turn = session.get_last_action_resolution()

        self.assertTrue(result.output_text.strip())
        self.assertNotIn("coming with you", result.output_text.lower())
        self.assertNotIn("stay nearby", result.output_text.lower())
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertIsNotNone(turn.social_outcome)
        assert turn.social_outcome is not None
        self.assertIn(
            turn.social_outcome.logistics_commitment,
            {
                LogisticsCommitment.ABSOLUTE_REFUSAL,
                LogisticsCommitment.DECLINE_JOIN,
                LogisticsCommitment.INDIRECT_SUPPORT,
                LogisticsCommitment.HIDDEN_SUPPORT,
            },
        )
        self.assertNotEqual(turn.social_outcome.logistics_commitment, LogisticsCommitment.NONE)


if __name__ == "__main__":
    unittest.main()
