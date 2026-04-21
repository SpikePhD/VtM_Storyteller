from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vampire_storyteller.action_resolution import ActionBlockReason, NormalizationSource, TurnOutcomeKind
from vampire_storyteller.dice_engine import DeterministicCheckKind
from vampire_storyteller.dice_engine import DeterministicCheckResolution
from vampire_storyteller.command_dispatcher import execute_command
from vampire_storyteller.command_models import ConversationStance, DialogueAct, TalkCommand
from vampire_storyteller.command_result import CommandResult
from vampire_storyteller.dialogue_adjudication import DialogueTopicStatus
from vampire_storyteller.dialogue_domain import DialogueDomain
from vampire_storyteller.dialogue_renderer import DialogueFactCard, DialogueRenderInput
from vampire_storyteller.dialogue_subtopic import DialogueSubtopic
from vampire_storyteller.game_session import GameSession
from vampire_storyteller.models import NPCDialogueProfile
from vampire_storyteller.narrative_provider import SceneNarrativeProvider
from vampire_storyteller.social_models import SocialOutcomeKind, SocialOutcomePacket, SocialStanceShift, TopicResult
from vampire_storyteller.world_state import WorldState


class RecordingSceneProvider(SceneNarrativeProvider):
    def __init__(self) -> None:
        self.rendered_world_times: list[str] = []

    def render_scene(self, world_state: WorldState) -> str:
        self.rendered_world_times.append(world_state.current_time)
        return f"rendered:{world_state.current_time}"


class GameSessionTests(unittest.TestCase):
    def test_default_session_builds_successfully(self) -> None:
        session = GameSession()
        world = session.get_world_state()
        self.assertIsNotNone(world)
        self.assertEqual(world.player.name, "Mara Vale")
        self.assertEqual(world.player.location_id, "loc_cafe")
        self.assertEqual(world.player.hunger, 2)
        self.assertEqual(world.player.stats["strength"], 2)

    def test_startup_text_is_non_empty(self) -> None:
        session = GameSession()
        self.assertTrue(session.get_startup_text().strip())

    def test_look_returns_non_quit_result(self) -> None:
        session = GameSession()
        result = session.process_input("look")

        self.assertIsInstance(result, CommandResult)
        self.assertFalse(result.should_quit)
        self.assertTrue(result.output_text.strip())

    def test_move_updates_session_world_state(self) -> None:
        session = GameSession()
        session.process_input("move loc_church")

        world = session.get_world_state()
        self.assertEqual(world.player.location_id, "loc_church")
        self.assertEqual(world.current_time, "2026-04-09T22:08:00+02:00")

    def test_move_to_invalid_destination_returns_explicit_feedback(self) -> None:
        session = GameSession()

        result = session.process_input("move loc_missing")
        turn = session.get_last_action_resolution()

        self.assertIn("Move is blocked", result.output_text)
        self.assertIn("loc_missing", result.output_text)
        self.assertFalse(result.render_scene)
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertTrue(turn.adjudication.is_blocked)
        self.assertEqual(turn.adjudication.block_reason, ActionBlockReason.INVALID_DESTINATION)

    def test_wait_updates_hunger_and_time(self) -> None:
        session = GameSession()
        session.process_input("wait 60")

        world = session.get_world_state()
        self.assertEqual(world.current_time, "2026-04-09T23:00:00+02:00")
        self.assertEqual(world.player.hunger, 3)

    def test_quit_returns_should_quit_true(self) -> None:
        session = GameSession()
        result = session.process_input("quit")
        self.assertTrue(result.should_quit)

    def test_unsupported_freeform_input_returns_explicit_failure(self) -> None:
        session = GameSession()

        result = session.process_input("sing a song")
        normalized = session.get_last_normalized_action()

        self.assertIn("Unsupported freeform input", result.output_text)
        self.assertFalse(result.render_scene)
        self.assertIsNotNone(normalized)
        assert normalized is not None
        self.assertEqual(normalized.source, NormalizationSource.FAILED)
        self.assertIsNone(normalized.command)
        self.assertIn("no freeform interpretation rule matched", normalized.failure_reason or "")

    def test_invalid_canonical_command_returns_explicit_failure(self) -> None:
        session = GameSession()

        result = session.process_input("talk")
        normalized = session.get_last_normalized_action()

        self.assertIn("Invalid canonical command", result.output_text)
        self.assertFalse(result.render_scene)
        self.assertIsNotNone(normalized)
        assert normalized is not None
        self.assertEqual(normalized.source, NormalizationSource.FAILED)
        self.assertIsNone(normalized.command)
        self.assertIn("talk requires exactly 1 npc_id argument", normalized.failure_reason or "")

    def test_investigate_while_premature_returns_explicit_feedback(self) -> None:
        session = GameSession()

        result = session.process_input("investigate")

        self.assertIn("Investigate is blocked", result.output_text)
        self.assertIn("Missing Ledger", result.output_text)
        self.assertIn("lead_confirmed", result.output_text)
        self.assertFalse(result.render_scene)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")
        self.assertEqual(len(session.get_world_state().event_log), 0)

    def test_investigate_at_dock_before_lead_confirmed_returns_explicit_feedback(self) -> None:
        session = GameSession()

        session.process_input("move loc_church")
        session.process_input("move loc_dock")
        result = session.process_input("investigate")

        self.assertIn("Investigate is blocked", result.output_text)
        self.assertIn("lead_confirmed", result.output_text)
        self.assertFalse(result.render_scene)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "church_visited")

    def test_talk_to_present_npc_returns_stable_dialogue_result(self) -> None:
        session = GameSession()

        result = session.process_input("talk npc_1")
        normalized = session.get_last_normalized_action()
        turn = session.get_last_action_resolution()

        self.assertTrue(result.output_text.strip())
        self.assertFalse(result.render_scene)
        self.assertEqual(session.get_world_state().player.location_id, "loc_cafe")
        self.assertEqual(session.get_world_state().npcs["npc_1"].trust_level, 1)
        self.assertEqual(session.get_conversation_focus_npc_id(), "npc_1")
        self.assertEqual(session.get_conversation_stance(), ConversationStance.NEUTRAL)
        self.assertIn("trust: 1", session.get_startup_text())
        self.assertIsNotNone(normalized)
        assert normalized is not None
        self.assertEqual(normalized.source, NormalizationSource.DIRECT_COMMAND)
        self.assertEqual(normalized.canonical_command_text, "talk npc_1")
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertEqual(turn.canonical_action_text, "talk npc_1")
        self.assertEqual(turn.normalization_source, NormalizationSource.DIRECT_COMMAND)
        self.assertEqual(turn.turn_kind, TurnOutcomeKind.STATEFUL_ACTION)

    def test_talk_greeting_uses_dialogue_metadata(self) -> None:
        session = GameSession()

        result = session.process_input("Jonas, good evening.")
        turn = session.get_last_action_resolution()

        self.assertEqual(result.output_text, "Evening.")
        self.assertIsNotNone(result.dialogue_presentation)
        assert result.dialogue_presentation is not None
        self.assertEqual(result.dialogue_presentation.player_utterance, "good evening.")
        self.assertEqual(result.dialogue_presentation.npc_display_name, "Jonas Reed")
        self.assertTrue(result.dialogue_presentation.focus_changed)
        self.assertEqual(session.get_world_state().npcs["npc_1"].trust_level, 0)
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertEqual(turn.normalization_source, NormalizationSource.INTERPRETED)
        self.assertEqual(turn.canonical_action_text, "talk npc_1")
        self.assertEqual(turn.turn_kind, TurnOutcomeKind.STATEFUL_ACTION)

    def test_follow_up_uses_conversation_focus(self) -> None:
        session = GameSession()

        session.process_input("Jonas, good evening.")
        result = session.process_input("Why?")
        interpreted = session.get_last_interpreted_input()

        self.assertIn("trail starts", result.output_text.lower())
        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertEqual(interpreted.dialogue_metadata.dialogue_act, DialogueAct.ASK)
        self.assertEqual(session.get_conversation_focus_npc_id(), "npc_1")

    def test_pronoun_follow_up_reuses_conversation_focus(self) -> None:
        session = GameSession()

        session.process_input("Jonas, good evening.")
        result = session.process_input("I turn back to her and continue.")
        interpreted = session.get_last_interpreted_input()

        self.assertTrue(result.output_text.strip())
        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertEqual(session.get_conversation_focus_npc_id(), "npc_1")

    def test_follow_up_unknownish_line_still_targets_focus(self) -> None:
        session = GameSession()

        session.process_input("Jonas, good evening.")
        result = session.process_input("I don't believe you.")
        interpreted = session.get_last_interpreted_input()
        turn = session.get_last_action_resolution()

        self.assertTrue(
            "not naming names" in result.output_text.lower()
            or "guarded" in result.output_text.lower()
        )
        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertEqual(interpreted.dialogue_metadata.dialogue_act, DialogueAct.ACCUSE)
        self.assertEqual(session.get_world_state().story_flags, [])
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")
        self.assertEqual(session.get_conversation_stance(), ConversationStance.GUARDED)
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertIsNotNone(turn.dialogue_adjudication)
        assert turn.dialogue_adjudication is not None
        self.assertTrue(turn.dialogue_adjudication.is_guarded)

    def test_follow_up_what_do_you_mean_stays_in_question_path(self) -> None:
        session = GameSession()

        session.process_input("Jonas, good evening.")
        result = session.process_input("What do you mean?")
        interpreted = session.get_last_interpreted_input()

        self.assertIn("trail starts", result.output_text.lower())
        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertEqual(interpreted.dialogue_metadata.dialogue_act, DialogueAct.ASK)
        self.assertEqual(session.get_conversation_stance(), ConversationStance.NEUTRAL)

    def test_background_follow_up_after_greeting_stays_with_jonas(self) -> None:
        session = GameSession()

        session.process_input("Hello Jonas, how's going?")
        result = session.process_input("Tell me more about you, what do you do?")
        interpreted = session.get_last_interpreted_input()

        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertIn("stay out of anybody's pocket", result.output_text.lower())
        self.assertNotIn("paper trail", result.output_text.lower())

    def test_dialogue_rendering_support_no_longer_depends_on_jonas_id(self) -> None:
        session = GameSession()
        render_input = DialogueRenderInput(
            npc_id="npc_2",
            npc_name="Sister Eliza",
            npc_role="Observer",
            player_name="Mara Vale",
            location_name="Blackthorn Cafe",
            utterance_text="Sister Eliza, what happened here?",
            speech_text="what happened here?",
            dialogue_act="ask",
            dialogue_domain="lead_topic",
            topic_status="productive",
            adjudication_resolution_kind="allowed",
            conversation_stance="neutral",
            conversation_subtopic=None,
            continuity_cue=None,
            npc_trust_level=0,
            plot_name="Missing Ledger",
            plot_stage="hook",
            lead_flag_active=False,
            check_kind=None,
            check_is_success=None,
            check_successes=None,
            check_difficulty=None,
            consequence_messages=(),
            applied_effects=(),
            npc_profile=NPCDialogueProfile(
                background_summary="Sister Eliza protects records and people.",
                public_persona="a guarded haven keeper",
                private_history_summary="She does not give much away.",
                motivations=["protect the church records"],
                speaking_style="measured and restrained",
                relationship_context="She is cautious with Mara.",
            ),
            authorized_fact_cards=(
                DialogueFactCard(
                    fact_id="test_fact",
                    kind="background",
                    summary="She stays measured and keeps her answer narrow.",
                ),
            ),
            social_outcome=SocialOutcomePacket(
                outcome_kind=SocialOutcomeKind.COOPERATE,
                stance_shift=SocialStanceShift(
                    from_stance=ConversationStance.NEUTRAL,
                    to_stance=ConversationStance.NEUTRAL,
                ),
                check_required=False,
                check_result=None,
                topic_result=TopicResult.UNCHANGED,
                state_effects=(),
                plot_effects=(),
                reason_code="test_packet",
            ),
        )

        self.assertTrue(session._supports_dialogue_rendering(render_input))

    def test_missing_ledger_follow_up_stays_in_the_same_subtopic(self) -> None:
        session = GameSession()

        session.process_input("Jonas, what happened at the dock?")
        result = session.process_input("What about it")
        interpreted = session.get_last_interpreted_input()
        turn = session.get_last_action_resolution()

        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertEqual(turn.canonical_action_text, "talk npc_1")
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.LEAD_TOPIC)
        self.assertEqual(session.get_conversation_focus_npc_id(), "npc_1")
        self.assertEqual(session.get_conversation_subtopic(), DialogueSubtopic.MISSING_LEDGER)
        self.assertNotIn("Unsupported freeform input", result.output_text)

    def test_guarded_follow_up_does_not_upgrade_missing_ledger_lane(self) -> None:
        session = GameSession()

        session.process_input("Jonas, what happened at the dock?")
        result = session.process_input("I don't believe you.")
        turn = session.get_last_action_resolution()

        self.assertEqual(turn.canonical_action_text, "talk npc_1")
        self.assertEqual(turn.dialogue_adjudication.topic_status, DialogueTopicStatus.REFUSED)
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.LEAD_PRESSURE)
        self.assertEqual(session.get_conversation_subtopic(), DialogueSubtopic.MISSING_LEDGER)
        self.assertTrue(
            "not naming names" in result.output_text.lower()
            or "guarded" in result.output_text.lower()
        )

    def test_backup_follow_up_stays_in_dialogue_without_repeating_name(self) -> None:
        session = GameSession()

        session.process_input("Jonas, good evening.")
        result = session.process_input("I need you as a back up")
        interpreted = session.get_last_interpreted_input()
        turn = session.get_last_action_resolution()

        self.assertIn("stay nearby", result.output_text.lower())
        self.assertNotIn("Unsupported freeform input", result.output_text)
        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertEqual(turn.canonical_action_text, "talk npc_1")
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.TRAVEL_PROPOSAL)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")
        self.assertEqual(session.get_world_state().story_flags, [])

    def test_acknowledged_backup_follow_up_stays_in_dialogue_without_repeating_name(self) -> None:
        session = GameSession()

        session.process_input("Jonas, what happened at the dock?")
        result = session.process_input("Yes we are. But I need you to back me up")
        interpreted = session.get_last_interpreted_input()
        turn = session.get_last_action_resolution()

        self.assertTrue("stay nearby" in result.output_text.lower() or "visible accomplice" in result.output_text.lower())
        self.assertNotIn("Unsupported freeform input", result.output_text)
        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertEqual(turn.canonical_action_text, "talk npc_1")
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.TRAVEL_PROPOSAL)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")
        self.assertEqual(session.get_world_state().story_flags, [])

    def test_named_backup_variant_still_works(self) -> None:
        session = GameSession()

        result = session.process_input("Jonas, I need you as a back up")
        turn = session.get_last_action_resolution()

        self.assertIn("nearby", result.output_text.lower())
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.TRAVEL_PROPOSAL)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")
        self.assertEqual(session.get_world_state().story_flags, [])

    def test_taxi_spare_change_follow_up_stays_in_dialogue_without_reusing_dock_lead(self) -> None:
        session = GameSession()

        session.process_input("talk npc_1")
        session.process_input("talk npc_1")
        plot_stage_before = session.get_world_state().plots["plot_1"].stage
        story_flags_before = list(session.get_world_state().story_flags)
        result = session.process_input("Ok then. I will call the taxi - do you have some spare change?")
        interpreted = session.get_last_interpreted_input()
        turn = session.get_last_action_resolution()

        self.assertIn("not financing the ride", result.output_text.lower())
        self.assertNotIn("paper trail began", result.output_text.lower())
        self.assertNotIn("dock is the only place worth checking", result.output_text.lower())
        self.assertNotIn("Unsupported freeform input", result.output_text)
        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertEqual(turn.canonical_action_text, "talk npc_1")
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.OFF_TOPIC_REQUEST)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, plot_stage_before)
        self.assertEqual(session.get_world_state().story_flags, story_flags_before)

    def test_taxi_money_follow_up_stays_in_dialogue_without_reusing_dock_lead(self) -> None:
        session = GameSession()

        session.process_input("talk npc_1")
        session.process_input("talk npc_1")
        plot_stage_before = session.get_world_state().plots["plot_1"].stage
        story_flags_before = list(session.get_world_state().story_flags)
        result = session.process_input("I don't have money to pay for the taxi to the dock!")
        interpreted = session.get_last_interpreted_input()
        turn = session.get_last_action_resolution()

        self.assertIn("not financing the ride", result.output_text.lower())
        self.assertNotIn("paper trail began", result.output_text.lower())
        self.assertNotIn("dock is the only place worth checking", result.output_text.lower())
        self.assertNotIn("Unsupported freeform input", result.output_text)
        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertEqual(turn.canonical_action_text, "talk npc_1")
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.OFF_TOPIC_REQUEST)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, plot_stage_before)
        self.assertEqual(session.get_world_state().story_flags, story_flags_before)

    def test_blood_refusal_follow_up_stays_in_off_topic_lane(self) -> None:
        session = GameSession()

        session.process_input("Jonas, I need blood before I go")
        plot_stage_before = session.get_world_state().plots["plot_1"].stage
        story_flags_before = list(session.get_world_state().story_flags)
        result = session.process_input("Why not - are you not eager to please a vampire?")
        turn = session.get_last_action_resolution()

        self.assertNotIn("dock is the only place worth checking", result.output_text.lower())
        self.assertNotIn("paper trail began", result.output_text.lower())
        self.assertIn("ask someone else", result.output_text.lower())
        self.assertEqual(turn.canonical_action_text, "talk npc_1")
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.OFF_TOPIC_REQUEST)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, plot_stage_before)
        self.assertEqual(session.get_world_state().story_flags, story_flags_before)

    def test_feed_persuade_follow_up_does_not_return_dock_lead(self) -> None:
        session = GameSession()

        result = session.process_input("I persuade Jonas into letting me feed off him")
        turn = session.get_last_action_resolution()

        self.assertNotIn("dock is the only place worth checking", result.output_text.lower())
        self.assertNotIn("paper trail began", result.output_text.lower())
        self.assertTrue("ask someone else" in result.output_text.lower() or "refuses" in result.output_text.lower())
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.OFF_TOPIC_REQUEST)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")
        self.assertEqual(session.get_world_state().story_flags, [])

    def test_transport_vehicle_question_stays_in_logistics_lane(self) -> None:
        session = GameSession()

        result = session.process_input("Jonas do you drive?")
        turn = session.get_last_action_resolution()

        self.assertTrue("ride" in result.output_text.lower() or "riding" in result.output_text.lower())
        self.assertNotIn("dock is the only place worth checking", result.output_text.lower())
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.TRAVEL_PROPOSAL)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")
        self.assertEqual(session.get_world_state().story_flags, [])

    def test_spare_car_follow_up_stays_in_transport_subtopic(self) -> None:
        session = GameSession()

        session.process_input("Jonas do you drive?")
        plot_stage_before = session.get_world_state().plots["plot_1"].stage
        story_flags_before = list(session.get_world_state().story_flags)
        result = session.process_input("Do you have a spare car?")
        turn = session.get_last_action_resolution()

        self.assertTrue("ride" in result.output_text.lower() or "riding" in result.output_text.lower())
        self.assertNotIn("dock is the only place worth checking", result.output_text.lower())
        self.assertEqual(turn.canonical_action_text, "talk npc_1")
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.TRAVEL_PROPOSAL)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, plot_stage_before)
        self.assertEqual(session.get_world_state().story_flags, story_flags_before)

    def test_short_please_follow_up_inherits_transport_subtopic(self) -> None:
        session = GameSession()

        session.process_input("Jonas do you drive?")
        result = session.process_input("Please?")
        turn = session.get_last_action_resolution()

        self.assertNotIn("dock is the only place worth checking", result.output_text.lower())
        self.assertEqual(turn.canonical_action_text, "talk npc_1")
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.TRAVEL_PROPOSAL)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")
        self.assertEqual(session.get_world_state().story_flags, [])

    def test_explicit_return_to_dock_restores_productive_lead_lane_after_transport(self) -> None:
        session = GameSession()

        session.process_input("Jonas do you drive?")
        result = session.process_input("What happened at the dock?")
        turn = session.get_last_action_resolution()

        self.assertIn("dock", result.output_text.lower())
        self.assertIn("paper trail", result.output_text.lower())
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.LEAD_TOPIC)

    def test_guarded_follow_up_go_on_does_not_unlock_productive_progression(self) -> None:
        session = GameSession()

        session.process_input("Jonas, good evening.")
        session.process_input("I don't believe you.")
        result = session.process_input("Go on.")

        self.assertNotIn("paper trail", result.output_text)
        self.assertNotIn("advanced from hook to lead_confirmed", result.output_text)
        self.assertEqual(session.get_world_state().story_flags, [])
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")
        self.assertEqual(session.get_conversation_stance(), ConversationStance.GUARDED)

    def test_clear_non_dialogue_action_is_not_swallowed_by_active_conversation(self) -> None:
        session = GameSession()

        session.process_input("Jonas, good evening.")
        result = session.process_input("I move to the church.")

        self.assertTrue(result.render_scene)
        self.assertEqual(session.get_world_state().player.location_id, "loc_church")

    def test_talk_question_uses_preserved_utterance_text(self) -> None:
        session = GameSession()

        result = session.process_input("I ask Jonas what happened here.")
        interpreted = session.get_last_interpreted_input()

        self.assertIsNotNone(interpreted)
        self.assertIsNotNone(interpreted.dialogue_metadata)
        self.assertIn("I ask Jonas what happened here.", interpreted.dialogue_metadata.utterance_text)
        self.assertIn("start with the dock", result.output_text.lower())
        self.assertEqual(session.get_world_state().npcs["npc_1"].trust_level, 0)

    def test_aggressive_talk_is_guarded(self) -> None:
        session = GameSession()

        accuse_result = session.process_input("I accuse Jonas of hiding something.")
        threaten_result = session.process_input("I threaten Jonas to talk.")
        threaten_turn = session.get_last_action_resolution()

        self.assertIn("guarded", accuse_result.output_text.lower())
        self.assertTrue(
            "guarded" in threaten_result.output_text.lower()
            or "keep this professional" in threaten_result.output_text.lower()
            or "watch your tone" in threaten_result.output_text.lower()
        )
        self.assertNotIn("said what he will say", threaten_result.output_text)
        self.assertIsNotNone(threaten_turn)
        assert threaten_turn is not None
        self.assertIsNotNone(threaten_turn.dialogue_adjudication)
        assert threaten_turn.dialogue_adjudication is not None
        self.assertTrue(threaten_turn.dialogue_adjudication.is_guarded)
        self.assertEqual(session.get_world_state().npcs["npc_1"].trust_level, 0)

    def test_persuade_routes_into_deterministic_social_check_and_advances_on_success(self) -> None:
        session = GameSession()

        with patch("vampire_storyteller.game_session.resolve_deterministic_check") as mock_resolve:
            mock_resolve.return_value = DeterministicCheckResolution(
                kind=DeterministicCheckKind.DIALOGUE_SOCIAL,
                seed="2026-04-09T22:00:00+02:00|talk|persuade|npc_1|dock|player_1|0|productive",
                roll_pool=3,
                difficulty=6,
                individual_rolls=[8, 2, 7],
                successes=2,
                is_success=True,
            )
            result = session.process_input("I persuade Jonas to help with the dock.")
        turn = session.get_last_action_resolution()

        self.assertIn("dock", result.output_text.lower())
        self.assertIn("paper trail", result.output_text.lower())
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertIsNotNone(turn.check)
        assert turn.check is not None
        self.assertEqual(turn.check.kind, DeterministicCheckKind.DIALOGUE_SOCIAL)
        self.assertTrue(turn.check.is_success)
        self.assertIsNotNone(turn.dialogue_adjudication)
        assert turn.dialogue_adjudication is not None
        self.assertTrue(turn.dialogue_adjudication.check_required)
        self.assertEqual(turn.dialogue_adjudication.reason_code, "persuade_check_required")
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.LEAD_PRESSURE)
        self.assertEqual(turn.adjudication.resolution_kind.name, "ROLL_GATED")
        self.assertIn("dialogue_social_check_success", turn.consequence_summary.applied_effects)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "lead_confirmed")
        self.assertIn("jonas_shared_dock_lead", session.get_world_state().story_flags)
        self.assertEqual(session.get_conversation_focus_npc_id(), "npc_1")

    def test_failed_persuade_stays_guarded_and_does_not_advance_plot(self) -> None:
        session = GameSession()

        with patch("vampire_storyteller.game_session.resolve_deterministic_check") as mock_resolve:
            mock_resolve.return_value = DeterministicCheckResolution(
                kind=DeterministicCheckKind.DIALOGUE_SOCIAL,
                seed="2026-04-09T22:00:00+02:00|talk|persuade|npc_1|dock|player_1|0|productive",
                roll_pool=3,
                difficulty=6,
                individual_rolls=[2, 3, 4],
                successes=0,
                is_success=False,
            )
            result = session.process_input("I persuade Jonas to help with the dock.")
        turn = session.get_last_action_resolution()

        self.assertIn("not getting more", result.output_text.lower())
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertIsNotNone(turn.check)
        assert turn.check is not None
        self.assertFalse(turn.check.is_success)
        self.assertIsNotNone(turn.dialogue_adjudication)
        assert turn.dialogue_adjudication is not None
        self.assertTrue(turn.dialogue_adjudication.check_required)
        self.assertEqual(turn.dialogue_adjudication.reason_code, "persuade_check_required")
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.LEAD_PRESSURE)
        self.assertIn("dialogue_social_check_failure", turn.consequence_summary.applied_effects)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")
        self.assertEqual(session.get_world_state().story_flags, [])
        self.assertEqual(session.get_conversation_stance(), ConversationStance.GUARDED)

    def test_jonas_dock_question_still_uses_productive_lead_path(self) -> None:
        session = GameSession()

        result = session.process_input("Jonas, what happened at the dock?")
        turn = session.get_last_action_resolution()

        self.assertIn("dock", result.output_text.lower())
        self.assertIn("paper trail", result.output_text.lower())
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertIsNotNone(turn.dialogue_adjudication)
        assert turn.dialogue_adjudication is not None
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.LEAD_TOPIC)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")

    def test_jonas_sex_request_does_not_reuse_dock_lead_or_advance_plot(self) -> None:
        session = GameSession()

        result = session.process_input("Jonas let us have sex")
        turn = session.get_last_action_resolution()

        self.assertIn("Keep this professional", result.output_text)
        self.assertNotIn("dock is the only place worth checking", result.output_text)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")
        self.assertEqual(session.get_world_state().story_flags, [])
        self.assertEqual(session.get_world_state().npcs["npc_1"].trust_level, 0)
        self.assertEqual(session.get_conversation_stance(), ConversationStance.GUARDED)
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertIsNotNone(turn.dialogue_adjudication)
        assert turn.dialogue_adjudication is not None
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.PROVOCATIVE_OR_INAPPROPRIATE)

    def test_jonas_blood_request_does_not_reuse_dock_lead_or_advance_plot(self) -> None:
        session = GameSession()

        result = session.process_input("Jonas I need blood")
        turn = session.get_last_action_resolution()

        self.assertIn("Ask someone else", result.output_text)
        self.assertNotIn("dock is the only place worth checking", result.output_text)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")
        self.assertEqual(session.get_world_state().story_flags, [])
        self.assertEqual(session.get_world_state().npcs["npc_1"].trust_level, 0)
        self.assertEqual(session.get_conversation_stance(), ConversationStance.NEUTRAL)
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertIsNotNone(turn.dialogue_adjudication)
        assert turn.dialogue_adjudication is not None
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.OFF_TOPIC_REQUEST)

    def test_jonas_travel_proposal_uses_distinct_logistics_response_without_plot_progress(self) -> None:
        session = GameSession()

        result = session.process_input("Jonas do you want to come with me to the docks?")
        turn = session.get_last_action_resolution()

        self.assertIn("if the dock matters, you go", result.output_text.lower())
        self.assertNotIn("dock is the only place worth checking", result.output_text)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")
        self.assertEqual(session.get_world_state().story_flags, [])
        self.assertEqual(session.get_world_state().npcs["npc_1"].trust_level, 0)
        self.assertEqual(session.get_conversation_stance(), ConversationStance.NEUTRAL)
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertIsNotNone(turn.dialogue_adjudication)
        assert turn.dialogue_adjudication is not None
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.TRAVEL_PROPOSAL)

    def test_jonas_tell_me_more_after_productive_success_stays_coherent(self) -> None:
        session = GameSession()

        first_result = session.process_input("talk npc_1")
        second_result = session.process_input("talk npc_1")
        follow_up_result = session.process_input("Jonas, please tell me more")
        turn = session.get_last_action_resolution()

        self.assertIn("dock", first_result.output_text.lower())
        self.assertIn("paper trail", second_result.output_text.lower())
        self.assertIn("trail starts", follow_up_result.output_text.lower())
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertIsNotNone(turn.dialogue_adjudication)
        assert turn.dialogue_adjudication is not None
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.LEAD_TOPIC)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "lead_confirmed")
        self.assertIn("trail starts", follow_up_result.output_text.lower())

    def test_guarded_blood_request_still_uses_off_topic_refusal(self) -> None:
        session = GameSession()

        session.process_input("I don't believe you.")
        result = session.process_input("Jonas I need blood")
        turn = session.get_last_action_resolution()

        self.assertIn("Ask someone else", result.output_text)
        self.assertNotIn("stays guarded and keeps the conversation tight", result.output_text)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")
        self.assertEqual(session.get_world_state().story_flags, [])
        self.assertEqual(session.get_conversation_stance(), ConversationStance.NEUTRAL)
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertIsNotNone(turn.dialogue_adjudication)
        assert turn.dialogue_adjudication is not None
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.OFF_TOPIC_REQUEST)

    def test_guarded_travel_request_still_uses_logistics_response(self) -> None:
        session = GameSession()

        session.process_input("I don't believe you.")
        result = session.process_input("Jonas do you want to come with me to the docks?")
        turn = session.get_last_action_resolution()

        self.assertIn("if the dock matters, you go", result.output_text.lower())
        self.assertNotIn("stays guarded and keeps the conversation tight", result.output_text)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")
        self.assertEqual(session.get_world_state().story_flags, [])
        self.assertEqual(session.get_conversation_stance(), ConversationStance.NEUTRAL)
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertIsNotNone(turn.dialogue_adjudication)
        assert turn.dialogue_adjudication is not None
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.TRAVEL_PROPOSAL)

    def test_guarded_provocative_line_keeps_its_specific_guarded_refusal(self) -> None:
        session = GameSession()

        session.process_input("I don't believe you.")
        result = session.process_input("Jonas let us have sex")
        turn = session.get_last_action_resolution()

        self.assertIn("Keep this professional", result.output_text)
        self.assertNotIn("stays guarded and keeps the conversation tight", result.output_text)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")
        self.assertEqual(session.get_world_state().story_flags, [])
        self.assertEqual(session.get_conversation_stance(), ConversationStance.GUARDED)
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertIsNotNone(turn.dialogue_adjudication)
        assert turn.dialogue_adjudication is not None
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.PROVOCATIVE_OR_INAPPROPRIATE)

    def test_move_clears_conversation_focus(self) -> None:
        session = GameSession()

        session.process_input("talk npc_1")
        session.process_input("move loc_church")

        self.assertIsNone(session.get_conversation_focus_npc_id())
        self.assertEqual(session.get_conversation_stance(), ConversationStance.NEUTRAL)
        self.assertIsNone(session.get_conversation_subtopic())
        result = session.process_input("Why?")

        self.assertIn("Talk is blocked", result.output_text)
        self.assertIn("not present at Saint Judith's Church", result.output_text)

    def test_move_clears_missing_ledger_subtopic(self) -> None:
        session = GameSession()

        session.process_input("Jonas, what happened at the dock?")
        session.process_input("move loc_church")

        self.assertIsNone(session.get_conversation_focus_npc_id())
        self.assertIsNone(session.get_conversation_subtopic())

    def test_explicit_new_topic_overrides_missing_ledger_subtopic(self) -> None:
        session = GameSession()

        session.process_input("Jonas, what happened at the dock?")
        result = session.process_input("Jonas, do you have a spare car?")
        interpreted = session.get_last_interpreted_input()
        turn = session.get_last_action_resolution()

        self.assertIn("visible accomplice", result.output_text.lower())
        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertEqual(turn.dialogue_adjudication.dialogue_domain, DialogueDomain.TRAVEL_PROPOSAL)
        self.assertEqual(session.get_conversation_subtopic(), DialogueSubtopic.TRANSPORT_OR_VEHICLE_SUPPORT)

    def test_follow_up_without_focus_returns_deterministic_feedback(self) -> None:
        session = GameSession()

        result = session.process_input("Go on.")

        self.assertEqual(result.output_text, "There is no active conversation to continue.")
        self.assertFalse(result.render_scene)
        self.assertIsNone(session.get_conversation_focus_npc_id())

    def test_question_without_focus_returns_deterministic_feedback(self) -> None:
        session = GameSession()

        result = session.process_input("Why?")

        self.assertEqual(result.output_text, "There is no active conversation to continue.")
        self.assertFalse(result.render_scene)

    def test_follow_up_phrase_without_focus_returns_deterministic_feedback(self) -> None:
        session = GameSession()

        result = session.process_input("What do you mean?")

        self.assertEqual(result.output_text, "There is no active conversation to continue.")
        self.assertFalse(result.render_scene)

    def test_load_clears_conversation_focus_and_stance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir) / "save.json"
            session = GameSession(save_path=save_path)

            session.process_input("talk npc_1")
            session.process_input("load")

            self.assertIsNone(session.get_conversation_focus_npc_id())
            self.assertEqual(session.get_conversation_stance(), ConversationStance.NEUTRAL)

    def test_follow_up_after_load_returns_stale_focus_feedback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir) / "save.json"
            session = GameSession(save_path=save_path)

            session.process_input("talk npc_1")
            session.process_input("save")
            session.process_input("load")
            result = session.process_input("Why?")

            self.assertIn("current conversation was reset when the save was loaded", result.output_text)
            self.assertFalse(result.render_scene)

    def test_explicit_other_npc_replaces_focus_when_available(self) -> None:
        session = GameSession()

        session.process_input("talk npc_1")
        session.process_input("move loc_church")
        result = session.process_input("Sister Eliza, good evening.")
        interpreted = session.get_last_interpreted_input()

        self.assertEqual(result.output_text, "Evening.")
        self.assertIsNotNone(result.dialogue_presentation)
        assert result.dialogue_presentation is not None
        self.assertEqual(result.dialogue_presentation.npc_display_name, "Sister Eliza")
        self.assertEqual(interpreted.target_reference, "npc_2")
        self.assertEqual(session.get_conversation_focus_npc_id(), "npc_2")

    def test_explicit_retarget_to_present_npc_after_focus_reset(self) -> None:
        session = GameSession()

        session.process_input("talk npc_1")
        session.process_input("move loc_church")
        result = session.process_input("Sister Eliza, we need to speak.")
        interpreted = session.get_last_interpreted_input()

        self.assertTrue(result.output_text.strip())
        self.assertIsNotNone(result.dialogue_presentation)
        assert result.dialogue_presentation is not None
        self.assertEqual(result.dialogue_presentation.npc_display_name, "Sister Eliza")
        self.assertEqual(interpreted.target_reference, "npc_2")
        self.assertEqual(session.get_conversation_focus_npc_id(), "npc_2")

    def test_natural_dialogue_to_absent_npc_returns_grounded_feedback(self) -> None:
        session = GameSession()

        result = session.process_input("Sister Eliza, we need to speak.")

        self.assertIn("Talk is blocked", result.output_text)
        self.assertIn("not present at Blackthorn Cafe", result.output_text)
        self.assertFalse(result.render_scene)

    def test_failed_explicit_retarget_clears_previous_focus_cleanly(self) -> None:
        session = GameSession()

        session.process_input("talk npc_1")
        result = session.process_input("talk npc_2")

        self.assertIn("Talk is blocked", result.output_text)
        self.assertIsNone(session.get_conversation_focus_npc_id())
        self.assertEqual(session.get_conversation_stance(), ConversationStance.NEUTRAL)

    def test_talk_can_shift_response_after_trust_improves(self) -> None:
        session = GameSession()

        first_result = session.process_input("talk npc_1")
        second_result = session.process_input("talk npc_1")

        self.assertIn("dock", first_result.output_text.lower())
        self.assertIn("paper trail", second_result.output_text.lower())
        self.assertIn("paper trail", second_result.output_text.lower())
        self.assertEqual(session.get_world_state().npcs["npc_1"].trust_level, 1)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "lead_confirmed")
        self.assertEqual(session.get_world_state().story_flags, ["jonas_shared_dock_lead"])

    def test_talk_one_shot_trust_hooks_do_not_stack_indefinitely(self) -> None:
        session = GameSession()

        session.process_input("talk npc_1")
        session.process_input("talk npc_1")
        session.process_input("talk npc_1")

        self.assertEqual(session.get_world_state().npcs["npc_1"].trust_level, 1)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "lead_confirmed")
        self.assertEqual(session.get_world_state().story_flags, ["jonas_shared_dock_lead"])

    def test_talk_to_absent_npc_returns_explicit_feedback(self) -> None:
        session = GameSession()

        result = session.process_input("talk npc_2")

        self.assertIn("Talk is blocked", result.output_text)
        self.assertIn("Sister Eliza", result.output_text)
        self.assertFalse(result.render_scene)

    def test_canonical_talk_without_metadata_still_works(self) -> None:
        session = GameSession()

        result = session.process_input("talk npc_1")

        self.assertTrue(result.output_text.strip())
        self.assertFalse(result.render_scene)

    def test_talk_uses_blocked_feedback_when_no_hook_matches_state(self) -> None:
        session = GameSession()

        session.process_input("move loc_church")
        session.process_input("wait 60")
        session.process_input("move loc_dock")
        session.process_input("investigate")
        result = session.process_input("talk npc_1")

        self.assertIn("Talk is blocked", result.output_text)
        self.assertIn("said what he will say", result.output_text)
        self.assertFalse(result.render_scene)
        self.assertIn("trust: 1", session.get_startup_text())

    def test_successful_investigate_updates_relevant_trust(self) -> None:
        session = GameSession()

        session.process_input("move loc_church")
        session.process_input("wait 60")
        session.process_input("move loc_dock")
        result = session.process_input("investigate")
        turn = session.get_last_action_resolution()

        self.assertTrue(result.render_scene)
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertIsNotNone(turn.check)
        assert turn.check is not None
        self.assertEqual(turn.check.kind, DeterministicCheckKind.INVESTIGATION)
        self.assertIsNotNone(turn.adjudication.check_spec)
        assert turn.adjudication.check_spec is not None
        self.assertEqual(turn.adjudication.check_spec.kind, DeterministicCheckKind.INVESTIGATION)
        self.assertIn("investigate_resolution_success", turn.consequence_summary.applied_effects)
        self.assertIn("plot_resolution_updated", turn.consequence_summary.applied_effects)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "resolved")
        self.assertIn("Plot 'Missing Ledger' resolved at North Dockside.", result.output_text)
        self.assertIn("Learned: The ledger's path points back to a hidden broker operating through the dock.", result.output_text)
        self.assertIn("Closing beat: Mara leaves North Dockside with the ledger matter settled.", result.output_text)
        self.assertEqual(session.get_world_state().npcs["npc_1"].trust_level, 1)
        self.assertEqual(session.get_world_state().npcs["npc_2"].trust_level, 1)
        self.assertEqual(session.get_world_state().story_flags, [])

    def test_save_load_restores_trust_reflected_in_scene_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir) / "save.json"
            session = GameSession(save_path=save_path)

            session.process_input("talk npc_1")
            session.process_input("save")

            reloaded_session = GameSession(save_path=save_path)
            load_result = reloaded_session.process_input("load")

            self.assertEqual(reloaded_session.get_world_state().npcs["npc_1"].trust_level, 1)
            self.assertIn("trust: 1", reloaded_session.get_startup_text())
            self.assertNotIn("Closing beat:", load_result.output_text)

    def test_injected_scene_provider_is_used_for_startup_and_mutations(self) -> None:
        provider = RecordingSceneProvider()
        session = GameSession(scene_provider=provider)

        startup_text = session.get_startup_text()
        look_result = session.process_input("look")
        move_result = session.process_input("move loc_church")

        self.assertEqual(startup_text, "rendered:2026-04-09T22:00:00+02:00")
        self.assertEqual(look_result.output_text, "rendered:2026-04-09T22:00:00+02:00")
        self.assertEqual(move_result.output_text, "rendered:2026-04-09T22:08:00+02:00")
        self.assertEqual(
            provider.rendered_world_times[:3],
            ["2026-04-09T22:00:00+02:00", "2026-04-09T22:00:00+02:00", "2026-04-09T22:08:00+02:00"],
        )

    def test_injected_scene_provider_is_used_after_wait_when_npcs_move(self) -> None:
        provider = RecordingSceneProvider()
        session = GameSession(scene_provider=provider)

        result = session.process_input("wait 60")

        self.assertEqual(result.output_text, "rendered:2026-04-09T23:00:00+02:00")
        self.assertEqual(provider.rendered_world_times[-1], "2026-04-09T23:00:00+02:00")
        self.assertEqual(session.get_world_state().npcs["npc_1"].location_id, "loc_dock")

    def test_help_status_and_quit_bypass_scene_provider(self) -> None:
        provider = RecordingSceneProvider()
        session = GameSession(scene_provider=provider)

        help_result = session.process_input("help")
        status_result = session.process_input("status")
        quit_result = session.process_input("quit")

        self.assertEqual(
            help_result.output_text.strip(),
            "look\nstatus\nhelp\nmove <destination_id>\nwait <minutes>\ntalk <npc_id>\ninvestigate\nsave\nload\nquit",
        )
        self.assertIn("Player:", status_result.output_text)
        self.assertTrue(quit_result.should_quit)
        self.assertEqual(provider.rendered_world_times, [])


if __name__ == "__main__":
    unittest.main()
