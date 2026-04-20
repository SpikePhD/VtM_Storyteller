from __future__ import annotations

import unittest
from unittest.mock import patch

from vampire_storyteller.config import AppConfig
from vampire_storyteller.cli import build_dialogue_renderer
from vampire_storyteller.command_models import ConversationStance
from vampire_storyteller.dialogue_renderer import (
    DeterministicDialogueRenderer,
    DialogueRenderInput,
    build_dialogue_render_input,
)
from vampire_storyteller.dice_engine import DeterministicCheckKind, DeterministicCheckResolution
from vampire_storyteller.game_session import GameSession
from vampire_storyteller.social_models import (
    SocialCheckResult,
    SocialOutcomeKind,
    SocialOutcomePacket,
    SocialStanceShift,
    TopicResult,
)


class FailingDialogueRenderer:
    def render_dialogue(self, render_input) -> str:
        raise RuntimeError("dialogue renderer failed")


def _make_render_input(
    *,
    outcome_kind: SocialOutcomeKind,
    topic_result: TopicResult,
    dialogue_domain: str = "lead_topic",
    dialogue_act: str = "greet",
    conversation_stance: str = "neutral",
    check_result: SocialCheckResult | None = None,
    check_kind: str | None = None,
    plot_stage: str = "hook",
    lead_flag_active: bool = False,
    applied_effects: tuple[str, ...] = (),
    plot_effects: tuple[str, ...] = (),
) -> DialogueRenderInput:
    return DialogueRenderInput(
        npc_id="npc_1",
        npc_name="Jonas Reed",
        npc_role="Informant",
        player_name="Mara Vale",
        location_name="Blackthorn Cafe",
        utterance_text="Jonas, what happened at the dock?",
        speech_text="what happened at the dock?",
        dialogue_act=dialogue_act,
        dialogue_domain=dialogue_domain,
        topic_status="productive" if topic_result is TopicResult.OPENED else "available" if topic_result is TopicResult.UNCHANGED else "refused",
        adjudication_resolution_kind="allowed",
        conversation_stance=conversation_stance,
        conversation_subtopic=None,
        npc_trust_level=0,
        plot_name="Missing Ledger",
        plot_stage=plot_stage,
        lead_flag_active=lead_flag_active,
        check_kind=check_kind,
        check_is_success=check_result.is_success if check_result is not None else None,
        check_successes=check_result.successes if check_result is not None else None,
        check_difficulty=check_result.difficulty if check_result is not None else None,
        consequence_messages=(),
        applied_effects=applied_effects,
        social_outcome=SocialOutcomePacket(
            outcome_kind=outcome_kind,
            stance_shift=SocialStanceShift(
                from_stance=ConversationStance.NEUTRAL,
                to_stance=ConversationStance.NEUTRAL if topic_result is not TopicResult.BLOCKED else ConversationStance.GUARDED,
            ),
            check_required=check_result is not None,
            check_result=check_result,
            topic_result=topic_result,
            state_effects=(),
            plot_effects=plot_effects,
            reason_code="test_packet",
        ),
    )


class DialogueRendererTests(unittest.TestCase):
    def test_productive_lead_reply_renders_from_structured_outcome(self) -> None:
        session = GameSession()

        result = session.process_input("Jonas, what happened at the dock?")

        self.assertIn("dock", result.output_text.lower())
        self.assertIn("jonas reed", result.output_text.lower())
        self.assertNotIn("Talk is guarded", result.output_text)

    def test_social_check_success_renders_from_structured_success_data(self) -> None:
        session = GameSession()

        with patch("vampire_storyteller.game_session.resolve_deterministic_check") as mock_resolve:
            mock_resolve.return_value = DeterministicCheckResolution(
                kind=DeterministicCheckKind.DIALOGUE_SOCIAL,
                seed="success-seed",
                roll_pool=3,
                difficulty=6,
                individual_rolls=[7, 8, 2],
                successes=2,
                is_success=True,
            )
            result = session.process_input("I persuade Jonas to help with the dock.")

        self.assertIn("waterline", result.output_text.lower())
        self.assertIn("broker", result.output_text.lower())
        self.assertNotIn("Dialogue check success", result.output_text)

    def test_social_check_failure_renders_from_structured_failure_data(self) -> None:
        session = GameSession()

        with patch("vampire_storyteller.game_session.resolve_deterministic_check") as mock_resolve:
            mock_resolve.return_value = DeterministicCheckResolution(
                kind=DeterministicCheckKind.DIALOGUE_SOCIAL,
                seed="failure-seed",
                roll_pool=3,
                difficulty=6,
                individual_rolls=[1, 3, 4],
                successes=0,
                is_success=False,
            )
            result = session.process_input("I persuade Jonas to help with the dock.")

        self.assertIn("guarded", result.output_text.lower())
        self.assertNotIn("Dialogue check failed", result.output_text)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")

    def test_provocative_refusal_renders_from_structured_domain_outcome(self) -> None:
        session = GameSession()

        result = session.process_input("Jonas let us have sex")

        self.assertIn("keep this professional", result.output_text.lower())
        self.assertNotIn("dock lead", result.output_text.lower())

    def test_travel_logistics_reply_renders_from_structured_domain_outcome(self) -> None:
        session = GameSession()

        result = session.process_input("Jonas do you want to come with me to the docks?")

        self.assertIn("if the dock matters, you go", result.output_text.lower())
        self.assertIn("noise", result.output_text.lower())

    def test_taxi_money_support_refusal_renders_from_structured_domain_outcome(self) -> None:
        session = GameSession()
        session.process_input("talk npc_1")
        session.process_input("talk npc_1")

        result = session.process_input("Ok then. I will call the taxi - do you have some spare change?")

        self.assertIn("not financing the ride", result.output_text.lower())
        self.assertNotIn("paper trail began", result.output_text.lower())

    def test_packet_first_greeting_does_not_force_dock_lead_reveal(self) -> None:
        renderer = DeterministicDialogueRenderer()
        render_input = _make_render_input(
            outcome_kind=SocialOutcomeKind.COOPERATE,
            topic_result=TopicResult.UNCHANGED,
            dialogue_act="greet",
        )

        output = renderer.render_dialogue(render_input)

        self.assertIn("brief nod", output.lower())
        self.assertNotIn("dock is where the paper trail began", output.lower())

    def test_packet_first_reveal_path_still_communicates_the_lead(self) -> None:
        renderer = DeterministicDialogueRenderer()
        render_input = _make_render_input(
            outcome_kind=SocialOutcomeKind.REVEAL,
            topic_result=TopicResult.OPENED,
            dialogue_act="ask",
            check_result=SocialCheckResult(
                kind="dialogue_social",
                seed="seed",
                roll_pool=3,
                difficulty=6,
                successes=2,
                is_success=True,
            ),
            check_kind="dialogue_social",
            lead_flag_active=True,
            plot_effects=("dialogue_plot_progressed",),
        )

        output = renderer.render_dialogue(render_input)

        self.assertIn("waterline", output.lower())
        self.assertIn("broker used the dock to move papers", output.lower())

    def test_packet_first_refusal_remains_guarded_without_progression(self) -> None:
        renderer = DeterministicDialogueRenderer()
        render_input = _make_render_input(
            outcome_kind=SocialOutcomeKind.REFUSE,
            topic_result=TopicResult.BLOCKED,
            dialogue_domain="provocative_or_inappropriate",
            dialogue_act="threaten",
        )

        output = renderer.render_dialogue(render_input)

        self.assertIn("keep this professional", output.lower())
        self.assertNotIn("paper trail began", output.lower())

    def test_packet_first_deflect_path_redirects_the_conversation(self) -> None:
        renderer = DeterministicDialogueRenderer()
        render_input = _make_render_input(
            outcome_kind=SocialOutcomeKind.DEFLECT,
            topic_result=TopicResult.PARTIAL,
            dialogue_domain="off_topic_request",
            dialogue_act="ask",
        )

        output = renderer.render_dialogue(render_input)

        self.assertIn("not that", output.lower())
        self.assertIn("ask someone else", output.lower())

    def test_packet_first_disengage_path_shuts_the_exchange_down(self) -> None:
        renderer = DeterministicDialogueRenderer()
        render_input = _make_render_input(
            outcome_kind=SocialOutcomeKind.DISENGAGE,
            topic_result=TopicResult.BLOCKED,
            dialogue_act="ask",
        )

        output = renderer.render_dialogue(render_input)

        self.assertIn("ends the exchange", output.lower())

    def test_packet_first_check_failure_is_reflected_naturally(self) -> None:
        renderer = DeterministicDialogueRenderer()
        render_input = _make_render_input(
            outcome_kind=SocialOutcomeKind.REFUSE,
            topic_result=TopicResult.BLOCKED,
            dialogue_act="persuade",
            check_result=SocialCheckResult(
                kind="dialogue_social",
                seed="seed",
                roll_pool=3,
                difficulty=6,
                successes=0,
                is_success=False,
            ),
            check_kind="dialogue_social",
        )

        output = renderer.render_dialogue(render_input)

        self.assertIn("stays guarded", output.lower())
        self.assertNotIn("broker used the dock to move papers", output.lower())

    def test_packet_first_check_success_is_reflected_naturally(self) -> None:
        renderer = DeterministicDialogueRenderer()
        render_input = _make_render_input(
            outcome_kind=SocialOutcomeKind.REVEAL,
            topic_result=TopicResult.OPENED,
            dialogue_act="persuade",
            check_result=SocialCheckResult(
                kind="dialogue_social",
                seed="seed",
                roll_pool=3,
                difficulty=6,
                successes=2,
                is_success=True,
            ),
            check_kind="dialogue_social",
            lead_flag_active=True,
            plot_effects=("dialogue_plot_progressed",),
        )

        output = renderer.render_dialogue(render_input)

        self.assertIn("pressure lands", output.lower())
        self.assertIn("broker used the dock to move papers", output.lower())

    def test_renderer_output_does_not_mutate_world_state(self) -> None:
        session = GameSession()
        session.process_input("Jonas, what happened at the dock?")
        turn = session.get_last_action_resolution()
        assert turn is not None
        assert turn.dialogue_adjudication is not None
        command = turn.normalized_action.command
        assert command is not None
        render_input = build_dialogue_render_input(
            session.get_world_state(),
            command,
            turn.dialogue_adjudication,
            turn.check,
            turn.consequence_summary,
            social_outcome=turn.social_outcome,
        )
        renderer = DeterministicDialogueRenderer()
        before = (
            session.get_world_state().plots["plot_1"].stage,
            tuple(session.get_world_state().story_flags),
            session.get_world_state().npcs["npc_1"].trust_level,
        )

        output = renderer.render_dialogue(render_input)

        after = (
            session.get_world_state().plots["plot_1"].stage,
            tuple(session.get_world_state().story_flags),
            session.get_world_state().npcs["npc_1"].trust_level,
        )
        self.assertTrue(output.strip())
        self.assertEqual(before, after)

    def test_session_falls_back_to_deterministic_dialogue_renderer_when_renderer_fails(self) -> None:
        session = GameSession(dialogue_renderer=FailingDialogueRenderer())

        result = session.process_input("Jonas, what happened at the dock?")

        self.assertIn("dock", result.output_text.lower())
        self.assertIn("jonas reed", result.output_text.lower())

    def test_dialogue_renderer_helper_uses_deterministic_renderer_when_openai_not_selected(self) -> None:
        renderer, notice = build_dialogue_renderer(
            AppConfig(
                openai_api_key=None,
                openai_model="gpt-4.1-mini",
                use_openai_scene_provider=False,
                use_openai_dialogue_intent_adapter=False,
                use_openai_dialogue_renderer=False,
            )
        )

        self.assertIsInstance(renderer, DeterministicDialogueRenderer)
        self.assertIsNone(notice)

    def test_missing_api_key_for_openai_dialogue_renderer_falls_back_safely(self) -> None:
        renderer, notice = build_dialogue_renderer(
            AppConfig(
                openai_api_key=None,
                openai_model="gpt-4.1-mini",
                use_openai_scene_provider=False,
                use_openai_dialogue_intent_adapter=False,
                use_openai_dialogue_renderer=True,
            )
        )

        self.assertIsInstance(renderer, DeterministicDialogueRenderer)
        self.assertIsNotNone(notice)
        self.assertIn("OPENAI_API_KEY is missing", notice)


if __name__ == "__main__":
    unittest.main()
