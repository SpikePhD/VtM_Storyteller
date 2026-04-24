from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from vampire_storyteller.cli import build_dialogue_renderer
from vampire_storyteller.config import AppConfig
from vampire_storyteller.conversation_context import DialogueHistoryEntry, DialogueMemoryContext
from vampire_storyteller.adventure_loader import load_adv1_dialogue_dossiers
from vampire_storyteller.dialogue_renderer import DialogueFactCard, DialogueRenderInput
from vampire_storyteller.models import NPCDialogueProfile
from vampire_storyteller.openai_dialogue_renderer import OpenAIDialogueRenderer
from vampire_storyteller.command_models import ConversationStance
from vampire_storyteller.social_models import (
    SocialCheckResult,
    SocialOutcomeKind,
    SocialOutcomePacket,
    SocialStanceShift,
    TopicResult,
)


def _minimal_render_input(
    *,
    utterance_text: str = "Jonas, what is it?",
    speech_text: str = "what is it?",
    dialogue_move: str = "continue",
) -> DialogueRenderInput:
    return DialogueRenderInput(
        npc_id="npc_1",
        npc_name="Jonas Reed",
        npc_role="Informant",
        player_name="Mara Vale",
        location_name="Blackthorn Cafe",
        utterance_text=utterance_text,
        speech_text=speech_text,
        dialogue_act="ask",
        dialogue_move=dialogue_move,
        dialogue_domain="meta_conversation",
        topic_status="available",
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
        npc_profile=NPCDialogueProfile(),
        npc_dossier=None,
        conversation_memory=DialogueMemoryContext(previous_interactions_summary="", recent_dialogue_history=()),
        authorized_fact_cards=(),
        social_outcome=None,
    )


class OpenAIDialogueRendererTests(unittest.TestCase):
    def test_renderer_can_be_constructed_with_mock_client(self) -> None:
        renderer = OpenAIDialogueRenderer(api_key="test-key", model="gpt-4.1-mini", client=Mock())

        self.assertIsNotNone(renderer)

    def test_renderer_builds_grounded_output_from_structured_payload(self) -> None:
        mock_client = Mock()
        mock_client.responses.create.return_value.output_text = "Storyteller dialogue text."
        renderer = OpenAIDialogueRenderer(api_key="test-key", model="gpt-4.1-mini", client=mock_client)

        output = renderer.render_dialogue(
            DialogueRenderInput(
                npc_id="npc_1",
                npc_name="Jonas Reed",
                npc_role="Informant",
                player_name="Mara Vale",
                location_name="Blackthorn Cafe",
                utterance_text="Jonas, what happened at the dock?",
                speech_text="what happened at the dock?",
                dialogue_act="ask",
                dialogue_move="continue",
                dialogue_domain="lead_topic",
                topic_status="productive",
                adjudication_resolution_kind="allowed",
                conversation_stance="neutral",
                conversation_subtopic=None,
                continuity_cue="follow_up_on_missing_ledger",
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
                    background_summary="Jonas trades in local knowledge.",
                    public_persona="a wary informant",
                    private_history_summary="He knows the dockside well.",
                    motivations=["stay useful"],
                    speaking_style="quiet and economical",
                    relationship_context="He is testing Mara.",
                ),
                npc_dossier=load_adv1_dialogue_dossiers().npc_definitions["npc_1"],
                conversation_memory=DialogueMemoryContext(
                    previous_interactions_summary="Mara and Jonas have talked before about the dock.",
                    recent_dialogue_history=(
                        DialogueHistoryEntry(speaker="player", utterance_text="Hello Jonas."),
                        DialogueHistoryEntry(speaker="Jonas Reed", utterance_text="Evening."),
                    ),
                ),
                authorized_fact_cards=(
                    DialogueFactCard(
                        fact_id="jonas_missing_ledger_lead",
                        kind="lead",
                        summary="He confirms that the missing ledger's trail begins at North Dockside.",
                    ),
                ),
                social_outcome=SocialOutcomePacket(
                    outcome_kind=SocialOutcomeKind.REVEAL,
                    stance_shift=SocialStanceShift(
                        from_stance=ConversationStance.NEUTRAL,
                        to_stance=ConversationStance.NEUTRAL,
                    ),
                    check_required=True,
                    check_result=SocialCheckResult(
                        kind="dialogue_social",
                        seed="seed",
                        roll_pool=3,
                        difficulty=6,
                        successes=2,
                        is_success=True,
                    ),
                    topic_result=TopicResult.OPENED,
                    state_effects=("dialogue_social_check_success",),
                    plot_effects=("dialogue_plot_progressed",),
                    reason_code="persuade_check_required",
                ),
            )
        )

        self.assertEqual(output, "Storyteller dialogue text.")
        called_kwargs = mock_client.responses.create.call_args.kwargs
        self.assertEqual(called_kwargs["model"], "gpt-4.1-mini")
        prompt = called_kwargs["input"]
        self.assertIn("social_outcome packet as the authoritative contract", prompt)
        self.assertIn("authorized_fact_cards are the only plot-facing facts", prompt)
        self.assertIn("Return speech-only output", prompt)
        self.assertIn("Write only the NPC's direct speech for this turn.", prompt)
        self.assertIn("Do not write third-person paraphrase", prompt)
        self.assertIn("Never put self-narration inside NPC speech", prompt)
        self.assertIn("there is no separate narration/action channel", prompt)
        self.assertIn("For vague discourse markers", prompt)
        self.assertIn("Do not merely restate the player's line", prompt)
        self.assertIn("Use dialogue_move to shape the line", prompt)
        self.assertIn("For statement-shaped turns, observations, insinuations, teasing, and meta pushback", prompt)
        self.assertIn("Do not mirror the player's wording and do not turn a statement into a follow-up question", prompt)
        self.assertIn("For simple greetings and acknowledgements", prompt)
        self.assertIn("continue should answer the exchange naturally", prompt)
        self.assertIn("Do not end every line with a handoff invitation.", prompt)
        self.assertIn("Prefer a concrete in-character reaction over filler", prompt)
        self.assertIn("Use npc_dossier for stable personality and relationship texture", prompt)
        self.assertIn("HIDDEN_SUPPORT is not an available logistics promise unless the payload explicitly contains that exact logistics_commitment", prompt)
        self.assertIn("do not imply hidden surveillance from refusals, deflections, or indirect support", prompt)
        self.assertIn("never say or imply 'watch from shadows'", prompt)
        self.assertIn("INDIRECT_SUPPORT means verbal or informational help only", prompt)
        self.assertIn("does not authorize surveillance, transport, accompaniment, waiting nearby, backup, or practical help", prompt)
        self.assertIn("Use npc_dossier.personality_guidance for speech style", prompt)
        self.assertIn("Personality guidance shapes tone, posture, and phrasing only", prompt)
        self.assertIn("Apply personality_guidance concretely at sentence level", prompt)
        self.assertIn("choose word count, sentence shape, directness, formality, and pushback style", prompt)
        self.assertIn("Do not inflate casual banter into poetic metaphor", prompt)
        self.assertIn("If banter_tolerance is low or very low", prompt)
        self.assertIn("acknowledge banter briefly, then redirect, set a boundary, or close the banter", prompt)
        self.assertIn("Avoid giving different NPCs the same refusal/support sentence shape", prompt)
        self.assertIn("do not soften refusals with vague ongoing support unless social_outcome.logistics_commitment explicitly authorizes that support", prompt)
        self.assertIn("previous_interactions_summary for longer-term relationship memory", prompt)
        self.assertIn("recent_dialogue_history for short-term continuity", prompt)
        self.assertIn("that is what I said", prompt)
        self.assertIn("you are looping", prompt)
        self.assertIn("Do not invent clue state, plot advancement, trust changes, NPC presence, permissions, legality, checks, or state changes.", prompt)
        self.assertIn('"npc_name":"Jonas Reed"', prompt)
        self.assertIn('"dialogue_domain":"lead_topic"', prompt)
        self.assertIn('"dialogue_move":"continue"', prompt)
        self.assertIn('"outcome_kind":"reveal"', prompt)
        self.assertIn('"check_result"', prompt)
        self.assertIn('"plot_name":"Missing Ledger"', prompt)
        self.assertIn('"authorized_fact_cards"', prompt)
        self.assertIn('"npc_dossier"', prompt)
        self.assertIn('"personality_guidance":', prompt)
        self.assertIn('"banter_tolerance":"low;', prompt)
        self.assertIn('"previous_interactions_summary":"Mara and Jonas have talked before about the dock."', prompt)
        self.assertIn('"recent_dialogue_history":[', prompt)

    def test_renderer_hard_fails_when_openai_response_has_no_text(self) -> None:
        mock_client = Mock()
        mock_client.responses.create.return_value.output_text = "   "
        renderer = OpenAIDialogueRenderer(api_key="test-key", model="gpt-4.1-mini", client=mock_client)

        with self.assertRaisesRegex(RuntimeError, "did not contain text"):
            renderer.render_dialogue(
                DialogueRenderInput(
                    npc_id="npc_1",
                    npc_name="Jonas Reed",
                    npc_role="Informant",
                    player_name="Mara Vale",
                    location_name="Blackthorn Cafe",
                    utterance_text="Jonas, what happened at the dock?",
                    speech_text="what happened at the dock?",
                    dialogue_act="ask",
                    dialogue_move="continue",
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
                        background_summary="Jonas trades in local knowledge.",
                        public_persona="a wary informant",
                        private_history_summary="He knows the dockside well.",
                        motivations=["stay useful"],
                        speaking_style="quiet and economical",
                        relationship_context="He is testing Mara.",
                    ),
                    npc_dossier=None,
                    conversation_memory=DialogueMemoryContext(
                        previous_interactions_summary="Mara and Jonas have talked before about the dock.",
                        recent_dialogue_history=(),
                    ),
                    authorized_fact_cards=(),
                    social_outcome=None,
                )
            )

    def test_renderer_rewrites_direct_echo_into_a_terse_repair_line(self) -> None:
        mock_client = Mock()
        mock_client.responses.create.return_value.output_text = "That is what I said."
        renderer = OpenAIDialogueRenderer(api_key="test-key", model="gpt-4.1-mini", client=mock_client)

        output = renderer.render_dialogue(
            DialogueRenderInput(
                npc_id="npc_1",
                npc_name="Jonas Reed",
                npc_role="Informant",
                player_name="Mara Vale",
                location_name="Blackthorn Cafe",
                utterance_text="Jonas, that is what I said.",
                speech_text="that is what I said.",
                dialogue_act="unknown",
                dialogue_move="clarify",
                dialogue_domain="meta_conversation",
                topic_status="refused",
                adjudication_resolution_kind="allowed",
                conversation_stance="guarded",
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
                    background_summary="Jonas trades in local knowledge.",
                    public_persona="a wary informant",
                    private_history_summary="He knows the dockside well.",
                    motivations=["stay useful"],
                    speaking_style="quiet and economical",
                    relationship_context="He is testing Mara.",
                ),
                npc_dossier=None,
                conversation_memory=DialogueMemoryContext(
                    previous_interactions_summary="Mara and Jonas have talked before about the dock.",
                    recent_dialogue_history=(),
                ),
                authorized_fact_cards=(),
                social_outcome=None,
            )
        )

        self.assertEqual(output, "I meant what I said.")

    def test_renderer_sanitizes_leading_self_narration_from_openai_output(self) -> None:
        mock_client = Mock()
        mock_client.responses.create.return_value.output_text = "Jonas Reed nods quietly. What is it?"
        renderer = OpenAIDialogueRenderer(api_key="test-key", model="gpt-4.1-mini", client=mock_client)

        output = renderer.render_dialogue(
            _minimal_render_input(
                utterance_text="Jonas, I need to ask you something.",
                speech_text="I need to ask you something.",
            )
        )

        self.assertEqual(output, "What is it?")

    def test_renderer_keeps_valid_first_person_speech(self) -> None:
        mock_client = Mock()
        mock_client.responses.create.return_value.output_text = "I hear you. What is it?"
        renderer = OpenAIDialogueRenderer(api_key="test-key", model="gpt-4.1-mini", client=mock_client)

        output = renderer.render_dialogue(_minimal_render_input())

        self.assertEqual(output, "I hear you. What is it?")

    def test_shared_dialogue_renderer_helper_uses_openai_model_from_runtime_config(self) -> None:
        with patch("vampire_storyteller.cli.OpenAIDialogueRenderer") as mock_renderer_ctor:
            renderer, notice = build_dialogue_renderer(
                AppConfig(
                    openai_api_key="test-key",
                    openai_model="gpt-4.1-mini",
                )
            )

        self.assertIsNone(notice)
        mock_renderer_ctor.assert_called_once_with(api_key="test-key", model="gpt-4.1-mini")
        self.assertIs(renderer, mock_renderer_ctor.return_value)

    def test_shared_dialogue_renderer_helper_requires_an_api_key(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "requires OPENAI_API_KEY"):
            build_dialogue_renderer(
                AppConfig(
                    openai_api_key=None,
                    openai_model="gpt-4.1-mini",
                )
            )


if __name__ == "__main__":
    unittest.main()
