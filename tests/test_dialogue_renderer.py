from __future__ import annotations

import unittest
from unittest.mock import patch

from vampire_storyteller.action_resolution import ActionConsequenceSummary
from vampire_storyteller.config import AppConfig
from vampire_storyteller.cli import build_dialogue_renderer
from vampire_storyteller.command_models import ConversationStance, DialogueAct, DialogueMetadata, TalkCommand
from vampire_storyteller.dialogue_context_assembler import DialogueTurnContext, assemble_dialogue_context
from vampire_storyteller.dialogue_renderer import (
    DialogueFactCard,
    DeterministicDialogueRenderer,
    DialogueRenderInput,
    build_dialogue_render_input,
)
from vampire_storyteller.conversation_context import DialogueHistoryEntry, DialogueMemoryContext
from vampire_storyteller.dice_engine import DeterministicCheckKind, DeterministicCheckResolution
from vampire_storyteller.game_session import GameSession
from vampire_storyteller.dialogue_adjudication import adjudicate_dialogue_talk
from vampire_storyteller.social_models import (
    LogisticsCommitment,
    SocialCheckResult,
    SocialOutcomeKind,
    SocialOutcomePacket,
    SocialStanceShift,
    TopicResult,
)
from vampire_storyteller.models import NPCDialogueProfile
from vampire_storyteller.sample_world import build_sample_world


class FailingDialogueRenderer:
    def render_dialogue(self, render_input) -> str:
        raise RuntimeError("dialogue renderer failed")


def _make_render_input(
    *,
    outcome_kind: SocialOutcomeKind,
    topic_result: TopicResult,
    npc_id: str = "npc_1",
    npc_name: str = "Jonas Reed",
    dialogue_domain: str = "lead_topic",
    dialogue_act: str = "greet",
    dialogue_move: str = "none",
    conversation_stance: str = "neutral",
    check_result: SocialCheckResult | None = None,
    check_kind: str | None = None,
    plot_stage: str = "hook",
    lead_flag_active: bool = False,
    applied_effects: tuple[str, ...] = (),
    plot_effects: tuple[str, ...] = (),
    authorized_fact_cards: tuple[DialogueFactCard, ...] = (),
    utterance_text: str = "Jonas, what happened at the dock?",
    speech_text: str = "what happened at the dock?",
    logistics_commitment: LogisticsCommitment = LogisticsCommitment.NONE,
) -> DialogueRenderInput:
    return DialogueRenderInput(
        npc_id=npc_id,
        npc_name=npc_name,
        npc_role="Informant",
        player_name="Mara Vale",
        location_name="Blackthorn Cafe",
        utterance_text=utterance_text,
        speech_text=speech_text,
        dialogue_act=dialogue_act,
        dialogue_move=dialogue_move,
        dialogue_domain=dialogue_domain,
        topic_status="productive" if topic_result is TopicResult.OPENED else "available" if topic_result is TopicResult.UNCHANGED else "refused",
        adjudication_resolution_kind="allowed",
        conversation_stance=conversation_stance,
        conversation_subtopic=None,
        continuity_cue=None,
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
        npc_profile=NPCDialogueProfile(
            background_summary="Jonas trades in local knowledge.",
            public_persona="a wary informant",
            private_history_summary="He knows the dockside well enough to avoid being seen there lightly.",
            motivations=["stay useful", "avoid exposure"],
            speaking_style="quiet and economical",
            relationship_context="He is testing Mara.",
        ),
        npc_dossier=None,
        conversation_memory=DialogueMemoryContext(
            previous_interactions_summary="Mara has already checked in with Jonas once.",
            recent_dialogue_history=(
                DialogueHistoryEntry(speaker="player", utterance_text="Hello Jonas."),
                DialogueHistoryEntry(speaker="Jonas Reed", utterance_text="Evening."),
            ),
        ),
        authorized_fact_cards=authorized_fact_cards,
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
            logistics_commitment=logistics_commitment,
        ),
        logistics_commitment=logistics_commitment,
    )


class DialogueRendererTests(unittest.TestCase):
    def assertNoUnsupportedLogisticsPromise(self, output: str) -> None:
        normalized_output = output.lower()
        for banned_term in ("watch", "shadows", "nearby", "backup", "cover", "keep an eye", "wait", "drive", "escort"):
            self.assertNotIn(banned_term, normalized_output)

    def test_productive_lead_reply_renders_from_structured_outcome(self) -> None:
        session = GameSession()

        session.process_input("/talk with Jonas")
        result = session.process_input("what happened at the dock?")

        self.assertIn("dock", result.output_text.lower())
        self.assertIn("trail", result.output_text.lower())
        self.assertNotIn("jonas reed", result.output_text.lower())

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
            session.process_input("/talk with Jonas")
            result = session.process_input("I persuade Jonas to help with the dock.")

        normalized_output = result.output_text.lower()
        self.assertIn("north dockside", normalized_output)
        self.assertTrue("paper trail" in normalized_output or "trail starts" in normalized_output)
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
            session.process_input("/talk with Jonas")
            result = session.process_input("I persuade Jonas to help with the dock.")

        self.assertTrue(result.output_text.strip())
        self.assertNotIn("Dialogue check failed", result.output_text)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")

    def test_provocative_refusal_renders_from_structured_domain_outcome(self) -> None:
        session = GameSession()

        session.process_input("/talk with Jonas")
        result = session.process_input("Jonas let us have sex")

        self.assertTrue(result.output_text.strip())
        self.assertNotIn("dock lead", result.output_text.lower())

    def test_travel_logistics_reply_renders_from_structured_domain_outcome(self) -> None:
        session = GameSession()

        session.process_input("/talk with Jonas")
        result = session.process_input("Jonas do you want to come with me to the docks?")

        self.assertTrue(result.output_text.strip())
        self.assertNotIn("paper trail", result.output_text.lower())
        self.assertNotIn("coming with you", result.output_text.lower())
        self.assertNotIn("stay nearby", result.output_text.lower())
        self.assertNotIn("visible accomplice", result.output_text.lower())

    def test_travel_boundary_refusal_renders_as_absolute_refusal(self) -> None:
        renderer = DeterministicDialogueRenderer()
        render_input = _make_render_input(
            outcome_kind=SocialOutcomeKind.REFUSE,
            topic_result=TopicResult.BLOCKED,
            dialogue_domain="travel_proposal",
            utterance_text="Jonas, are you coming with?",
            speech_text="are you coming with?",
            logistics_commitment=LogisticsCommitment.ABSOLUTE_REFUSAL,
        )

        output = renderer.render_dialogue(render_input)

        self.assertIn("absolutely not", output.lower())
        self.assertNotIn("coming with you", output.lower())

    def test_travel_boundary_indirect_support_stays_bounded(self) -> None:
        renderer = DeterministicDialogueRenderer()
        render_input = _make_render_input(
            outcome_kind=SocialOutcomeKind.COOPERATE,
            topic_result=TopicResult.PARTIAL,
            dialogue_domain="travel_proposal",
            utterance_text="Ok, start your car, you are driving me there.",
            speech_text="ok, start your car, you are driving me there.",
            logistics_commitment=LogisticsCommitment.INDIRECT_SUPPORT,
        )

        output = renderer.render_dialogue(render_input)

        self.assertIn("information", output.lower())
        self.assertIn("not driving you", output.lower())
        self.assertNotIn("coming with you", output.lower())

    def test_travel_boundary_hidden_support_legacy_input_stays_conservative(self) -> None:
        renderer = DeterministicDialogueRenderer()
        render_input = _make_render_input(
            outcome_kind=SocialOutcomeKind.COOPERATE,
            topic_result=TopicResult.PARTIAL,
            dialogue_domain="travel_proposal",
            utterance_text="I know you are dependable and you work well. Just come with.",
            speech_text="i know you are dependable and you work well. just come with.",
            logistics_commitment=LogisticsCommitment.HIDDEN_SUPPORT,
        )

        output = renderer.render_dialogue(render_input)

        self.assertNoUnsupportedLogisticsPromise(output)
        self.assertNotIn("coming with you", output.lower())

    def test_taxi_money_support_refusal_renders_from_structured_domain_outcome(self) -> None:
        session = GameSession()
        session.process_input("/talk npc_1")
        session.process_input("/talk npc_1")

        result = session.process_input("Ok then. I will call the taxi - do you have some spare change?")

        self.assertTrue(result.output_text.strip())
        self.assertNotIn("paper trail", result.output_text.lower())
        self.assertNotIn("paper trail began", result.output_text.lower())

    def test_dialogue_context_assembler_returns_jonas_dossier_backed_context(self) -> None:
        world_state = build_sample_world()
        command = TalkCommand(
            npc_id="npc_1",
            dialogue_metadata=DialogueMetadata(
                utterance_text="Jonas, what happened at the dock?",
                speech_text="what happened at the dock?",
                dialogue_act=DialogueAct.ASK,
                topic="dock",
            ),
        )
        adjudication = adjudicate_dialogue_talk(world_state, command)

        context = assemble_dialogue_context(
            world_state,
            command,
            adjudication,
            adjudication.social_outcome,
            (),
        )

        self.assertEqual(context.npc_id, "npc_1")
        self.assertEqual(context.npc_name, "Jonas Reed")
        self.assertEqual(context.location_name, "Blackthorn Cafe")
        self.assertEqual(context.plot_id, "plot_1")
        self.assertEqual(context.plot_stage, "hook")
        self.assertEqual(context.conversation_stance, "neutral")
        self.assertIsNotNone(context.npc_dossier)
        assert context.npc_dossier is not None
        self.assertEqual(context.npc_dossier.public_persona, "a wary neighborhood informant who keeps public conversations short")
        self.assertIn("terse", context.npc_dossier.personality_guidance.speech_style)
        self.assertIn("indirect", context.npc_dossier.personality_guidance.directness_preference)
        self.assertEqual(context.npc_dossier.revealable_fact_groups[0].fact_ids, ("jonas_missing_ledger_lead",))

    def test_dialogue_context_assembler_returns_eliza_dossier_backed_context(self) -> None:
        world_state = build_sample_world()
        world_state.player.location_id = "loc_church"
        world_state.plots["plot_1"].stage = "church_visited"
        command = TalkCommand(
            npc_id="npc_2",
            dialogue_metadata=DialogueMetadata(
                utterance_text="Sister Eliza, what about the church records?",
                speech_text="what about the church records?",
                dialogue_act=DialogueAct.ASK,
                topic="church_records",
            ),
        )
        adjudication = adjudicate_dialogue_talk(world_state, command)

        context = assemble_dialogue_context(
            world_state,
            command,
            adjudication,
            adjudication.social_outcome,
            (),
        )

        self.assertEqual(context.npc_id, "npc_2")
        self.assertEqual(context.npc_name, "Sister Eliza")
        self.assertIsNotNone(context.npc_dossier)
        assert context.npc_dossier is not None
        self.assertEqual(context.npc_dossier.public_persona, "a guarded haven keeper who weighs every question before answering")
        self.assertIn("measured", context.npc_dossier.personality_guidance.speech_style)
        self.assertIn("firm boundaries", context.npc_dossier.personality_guidance.confrontation_style)
        self.assertEqual(context.npc_dossier.topic_groups[0].group_id, "church_records")
        self.assertEqual(context.npc_profile.public_persona, "a guarded haven keeper who watches before she speaks")

    def test_build_dialogue_render_input_uses_eliza_church_records_facts(self) -> None:
        world_state = build_sample_world()
        world_state.player.location_id = "loc_church"
        world_state.plots["plot_1"].stage = "church_visited"
        command = TalkCommand(
            npc_id="npc_2",
            dialogue_metadata=DialogueMetadata(
                utterance_text="Sister Eliza, what about the church records?",
                speech_text="what about the church records?",
                dialogue_act=DialogueAct.ASK,
                topic="church_records",
            ),
        )
        adjudication = adjudicate_dialogue_talk(world_state, command)

        render_input = build_dialogue_render_input(
            world_state,
            command,
            adjudication,
            None,
            ActionConsequenceSummary(),
            social_outcome=adjudication.social_outcome,
        )

        self.assertEqual(render_input.npc_name, "Sister Eliza")
        self.assertEqual(render_input.dialogue_domain, "lead_topic")
        self.assertEqual(render_input.topic_status, "productive")
        self.assertIsNotNone(render_input.npc_dossier)
        assert render_input.npc_dossier is not None
        self.assertIn("measured", render_input.npc_dossier.personality_guidance.speech_style)
        self.assertIn("eliza_church_records_lead", [fact.fact_id for fact in render_input.authorized_fact_cards])
        self.assertIn("eliza_church_records_follow_up", [fact.fact_id for fact in render_input.authorized_fact_cards])

    def test_build_dialogue_render_input_uses_assembled_dialogue_context(self) -> None:
        session = GameSession()
        session.process_input("/talk with Jonas")
        session.process_input("what happened at the dock?")
        turn = session.get_last_action_resolution()
        assert turn is not None
        assert turn.dialogue_adjudication is not None
        command = turn.normalized_action.command
        assert command is not None

        assembled_context = DialogueTurnContext(
            npc_id="npc_1",
            npc_name="Assembled Jonas",
            npc_role="Assembler Role",
            npc_trust_level=7,
            npc_profile=NPCDialogueProfile(
                background_summary="assembled background",
                public_persona="assembled persona",
                private_history_summary="assembled history",
                motivations=["assembled motivation"],
                speaking_style="assembled style",
                relationship_context="assembled relationship",
            ),
            npc_dossier=None,
            conversation_memory=DialogueMemoryContext(
                previous_interactions_summary="assembled summary",
                recent_dialogue_history=(
                    DialogueHistoryEntry(speaker="player", utterance_text="Hello."),
                ),
            ),
            player_name="Assembled Player",
            location_name="Assembled Cafe",
            plot_id="plot_1",
            plot_name="Assembled Plot",
            plot_stage="lead_confirmed",
            lead_flag_active=True,
            conversation_stance="guarded",
            conversation_subtopic="missing_ledger",
            social_outcome=turn.social_outcome,
            authorized_fact_cards=(
                DialogueFactCard(
                    fact_id="assembled_fact",
                    kind="lead",
                    summary="Assembled summary",
                    render_specificity="vague_rumor",
                ),
            ),
        )

        with patch("vampire_storyteller.dialogue_renderer.assemble_dialogue_context", return_value=assembled_context) as mock_assemble:
            render_input = build_dialogue_render_input(
                session.get_world_state(),
                command,
                turn.dialogue_adjudication,
                turn.check,
                turn.consequence_summary,
                social_outcome=turn.social_outcome,
            )

        mock_assemble.assert_called_once()
        self.assertEqual(render_input.npc_name, "Assembled Jonas")
        self.assertEqual(render_input.location_name, "Assembled Cafe")
        self.assertEqual(render_input.npc_profile.public_persona, "assembled persona")
        self.assertEqual(render_input.conversation_memory.previous_interactions_summary, "assembled summary")
        self.assertEqual(
            render_input.conversation_memory.recent_dialogue_history,
            (DialogueHistoryEntry(speaker="player", utterance_text="Hello."),),
        )
        self.assertEqual(render_input.plot_stage, "lead_confirmed")
        self.assertEqual(render_input.conversation_subtopic, "missing_ledger")
        self.assertEqual(render_input.authorized_fact_cards[0].fact_id, "assembled_fact")

    def test_packet_first_greeting_does_not_force_dock_lead_reveal(self) -> None:
        renderer = DeterministicDialogueRenderer()
        render_input = _make_render_input(
            outcome_kind=SocialOutcomeKind.COOPERATE,
            topic_result=TopicResult.UNCHANGED,
            dialogue_act="greet",
            utterance_text="Jonas, good evening.",
            speech_text="good evening.",
        )

        output = renderer.render_dialogue(render_input)

        self.assertIn("evening", output.lower())
        self.assertNotIn("dock", output.lower())

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
            authorized_fact_cards=(
                DialogueFactCard(
                    fact_id="jonas_missing_ledger_lead",
                    kind="lead",
                    summary="He confirms that the missing ledger's trail begins at North Dockside.",
                    render_specificity="confirmed_lead",
                ),
            ),
        )

        output = renderer.render_dialogue(render_input)

        self.assertIn("dockside", output.lower())
        self.assertIn("piece you get", output.lower())
        self.assertNotIn("broker used the dock to move papers", output.lower())

    def test_packet_first_lead_summary_stays_vague_without_actionable_specificity(self) -> None:
        renderer = DeterministicDialogueRenderer()
        render_input = _make_render_input(
            outcome_kind=SocialOutcomeKind.DEFLECT,
            topic_result=TopicResult.PARTIAL,
            dialogue_domain="lead_topic",
            dialogue_act="ask",
            utterance_text="I need to know about the ledger.",
            speech_text="i need to know about the ledger.",
            authorized_fact_cards=(
                DialogueFactCard(
                    fact_id="jonas_missing_ledger_lead",
                    kind="lead",
                    summary="He confirms that the missing ledger's trail begins at North Dockside.",
                    render_specificity="vague_rumor",
                    render_summary="There is a rumor here, but nothing concrete is being given away yet.",
                ),
            ),
        )

        output = renderer.render_dialogue(render_input)

        self.assertNotIn("north dockside", output.lower())
        self.assertNotIn("trail starts", output.lower())
        self.assertIn("not the part", output.lower())

    def test_packet_first_refusal_remains_guarded_without_progression(self) -> None:
        renderer = DeterministicDialogueRenderer()
        render_input = _make_render_input(
            outcome_kind=SocialOutcomeKind.REFUSE,
            topic_result=TopicResult.BLOCKED,
            dialogue_domain="provocative_or_inappropriate",
            dialogue_act="threaten",
            authorized_fact_cards=(
                DialogueFactCard(
                    fact_id="jonas_provocative_boundary",
                    kind="boundary",
                    summary="He treats provocative pressure as a reason to harden immediately and shut the conversation back down.",
                ),
            ),
        )

        output = renderer.render_dialogue(render_input)

        self.assertIn("keep this professional", output.lower())

    def test_packet_first_meta_conversation_challenge_stays_out_of_the_content_lane(self) -> None:
        renderer = DeterministicDialogueRenderer()
        render_input = _make_render_input(
            outcome_kind=SocialOutcomeKind.DEFLECT,
            topic_result=TopicResult.PARTIAL,
            dialogue_domain="meta_conversation",
            dialogue_act="ask",
            utterance_text="Why are you so hostile?",
            speech_text="why are you so hostile?",
        )

        output = renderer.render_dialogue(render_input)

        self.assertNotIn("paper trail", output.lower())
        self.assertNotIn("dockside", output.lower())

    def test_statement_react_move_renders_without_echoing_player_text(self) -> None:
        renderer = DeterministicDialogueRenderer()
        render_input = _make_render_input(
            outcome_kind=SocialOutcomeKind.COOPERATE,
            topic_result=TopicResult.UNCHANGED,
            dialogue_act="greet",
            dialogue_move="react",
            utterance_text="Jonas, just coming to say hi.",
            speech_text="just coming to say hi.",
        )

        output = renderer.render_dialogue(render_input)

        self.assertTrue(output.strip())
        self.assertNotIn("coming to say hi", output.lower())
        self.assertNotIn("?", output)

    def test_statement_react_move_does_not_default_to_a_follow_up_question(self) -> None:
        renderer = DeterministicDialogueRenderer()
        render_input = _make_render_input(
            outcome_kind=SocialOutcomeKind.COOPERATE,
            topic_result=TopicResult.UNCHANGED,
            dialogue_act="greet",
            dialogue_move="react",
            utterance_text="Jonas, how are you holding up?",
            speech_text="how are you holding up?",
        )

        output = renderer.render_dialogue(render_input)

        self.assertEqual(output, "I'm holding up.")
        self.assertNotIn("?", output)

    def test_statement_continue_move_renders_without_echoing_player_text(self) -> None:
        renderer = DeterministicDialogueRenderer()
        render_input = _make_render_input(
            outcome_kind=SocialOutcomeKind.REFUSE,
            topic_result=TopicResult.BLOCKED,
            dialogue_domain="meta_conversation",
            dialogue_act="unknown",
            dialogue_move="continue",
            utterance_text="Jonas, sure. Tell me.",
            speech_text="sure. tell me.",
        )

        output = renderer.render_dialogue(render_input)

        self.assertTrue(output.strip())
        self.assertNotIn("sure. tell me", output.lower())
        self.assertNotIn("go on", output.lower())
        self.assertNotIn("i'm listening", output.lower())

    def test_statement_clarify_move_renders_without_echoing_player_text(self) -> None:
        renderer = DeterministicDialogueRenderer()
        render_input = _make_render_input(
            outcome_kind=SocialOutcomeKind.REFUSE,
            topic_result=TopicResult.BLOCKED,
            dialogue_domain="meta_conversation",
            dialogue_act="unknown",
            dialogue_move="clarify",
            utterance_text="Jonas, you just did.",
            speech_text="you just did.",
        )

        output = renderer.render_dialogue(render_input)

        self.assertTrue(output.strip())
        self.assertNotIn("you just did", output.lower())
        self.assertNotIn("paper trail", output.lower())
        self.assertNotIn("?", output)

    def test_statement_clarify_meta_looping_renders_without_echoing_player_text_or_question(self) -> None:
        renderer = DeterministicDialogueRenderer()
        render_input = _make_render_input(
            outcome_kind=SocialOutcomeKind.DEFLECT,
            topic_result=TopicResult.PARTIAL,
            dialogue_domain="meta_conversation",
            dialogue_act="unknown",
            dialogue_move="clarify",
            utterance_text="Jonas, you are looping.",
            speech_text="you are looping.",
        )

        output = renderer.render_dialogue(render_input)

        self.assertTrue(output.strip())
        self.assertNotIn("you are looping", output.lower())
        self.assertNotIn("?", output)

    def test_statement_banter_move_renders_without_echoing_player_text(self) -> None:
        renderer = DeterministicDialogueRenderer()
        render_input = _make_render_input(
            outcome_kind=SocialOutcomeKind.REFUSE,
            topic_result=TopicResult.BLOCKED,
            dialogue_domain="meta_conversation",
            dialogue_act="unknown",
            dialogue_move="banter",
            utterance_text="Jonas, there you are! anyhow, I know you have information for me.",
            speech_text="there you are! anyhow, I know you have information for me.",
        )

        output = renderer.render_dialogue(render_input)

        self.assertTrue(output.strip())
        self.assertNotIn("there you are", output.lower())

    def test_packet_first_refusal_renders_without_jonas_specific_gate(self) -> None:
        renderer = DeterministicDialogueRenderer()
        render_input = _make_render_input(
            outcome_kind=SocialOutcomeKind.REFUSE,
            topic_result=TopicResult.BLOCKED,
            npc_id="npc_2",
            npc_name="Sister Eliza",
            dialogue_domain="lead_pressure",
            dialogue_act="ask",
        )

        output = renderer.render_dialogue(render_input)

        self.assertIn("all you're getting", output.lower())
        self.assertNotIn("jonas", output.lower())

    def test_packet_first_deflect_path_redirects_the_conversation(self) -> None:
        renderer = DeterministicDialogueRenderer()
        render_input = _make_render_input(
            outcome_kind=SocialOutcomeKind.DEFLECT,
            topic_result=TopicResult.PARTIAL,
            dialogue_domain="off_topic_request",
            dialogue_act="ask",
            authorized_fact_cards=(
                DialogueFactCard(
                    fact_id="jonas_money_boundary",
                    kind="boundary",
                    summary="He refuses to finance the trip and does not want the conversation drifting into favors that expose him.",
                ),
            ),
        )

        output = renderer.render_dialogue(render_input)

        self.assertIn("financing the ride", output.lower())

    def test_packet_first_disengage_path_shuts_the_exchange_down(self) -> None:
        renderer = DeterministicDialogueRenderer()
        render_input = _make_render_input(
            outcome_kind=SocialOutcomeKind.DISENGAGE,
            topic_result=TopicResult.BLOCKED,
            dialogue_act="ask",
        )

        output = renderer.render_dialogue(render_input)

        self.assertIn("done here", output.lower())

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
            authorized_fact_cards=(
                DialogueFactCard(
                    fact_id="jonas_check_failure_guarded",
                    kind="refusal_basis",
                    summary="When the push fails, he goes guarded again and gives Mara nothing beyond the fact that she is not getting more tonight.",
                ),
            ),
        )

        output = renderer.render_dialogue(render_input)

        self.assertIn("not getting more", output.lower())
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
            authorized_fact_cards=(
                DialogueFactCard(
                    fact_id="jonas_check_success_reveal",
                    kind="lead",
                    summary="Under real pressure he admits the dock lead plainly enough for Mara to act on it.",
                    render_specificity="confirmed_lead",
                ),
            ),
        )

        output = renderer.render_dialogue(render_input)

        self.assertIn("paper trail", output.lower())
        self.assertIn("dock", output.lower())
        self.assertIn("piece you get", output.lower())

    def test_packet_first_check_success_without_authorized_lead_stays_generic(self) -> None:
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
            authorized_fact_cards=(
                DialogueFactCard(
                    fact_id="jonas_missing_ledger_lead",
                    kind="lead",
                    summary="He confirms that the missing ledger's trail begins at North Dockside.",
                    render_specificity="vague_rumor",
                ),
            ),
        )

        output = renderer.render_dialogue(render_input)

        self.assertNotIn("north dockside", output.lower())
        self.assertNotIn("trail starts", output.lower())
        self.assertIn("move on", output.lower())

    def test_renderer_output_does_not_mutate_world_state(self) -> None:
        session = GameSession()
        session.process_input("/talk with Jonas")
        session.process_input("what happened at the dock?")
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

    def test_session_returns_explicit_render_failure_when_renderer_fails(self) -> None:
        session = GameSession(dialogue_renderer=FailingDialogueRenderer())

        session.process_input("/talk with Jonas")
        result = session.process_input("what happened at the dock?")

        self.assertIn("dialogue rendering failed", result.output_text.lower())

    def test_dialogue_renderer_helper_uses_openai_model_from_runtime_config(self) -> None:
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

    def test_missing_api_key_for_openai_dialogue_renderer_hard_fails_explicitly(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "requires OPENAI_API_KEY"):
            build_dialogue_renderer(
                AppConfig(
                    openai_api_key=None,
                    openai_model="gpt-4.1-mini",
                )
            )

    def test_renderer_failure_stays_explicit_when_openai_renderer_is_available(self) -> None:
        with patch("vampire_storyteller.cli.OpenAIDialogueRenderer", return_value=FailingDialogueRenderer()) as mock_renderer_ctor:
            renderer, notice = build_dialogue_renderer(
                AppConfig(
                    openai_api_key="test-key",
                    openai_model="gpt-4.1-mini",
                )
            )

        with self.assertRaisesRegex(RuntimeError, "dialogue renderer failed"):
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
                    npc_dossier=None,
                    conversation_memory=DialogueMemoryContext(
                        previous_interactions_summary="Mara has already traded one greeting with Jonas.",
                        recent_dialogue_history=(),
                    ),
                    authorized_fact_cards=(),
                    social_outcome=None,
                )
            )

        self.assertIsNone(notice)
        mock_renderer_ctor.assert_called_once_with(api_key="test-key", model="gpt-4.1-mini")


if __name__ == "__main__":
    unittest.main()
