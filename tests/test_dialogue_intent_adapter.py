from __future__ import annotations

import unittest
from unittest.mock import Mock

from vampire_storyteller.command_models import DialogueAct
from vampire_storyteller.dialogue_intent_adapter import (
    DialogueIntentContext,
    DialogueIntentProposal,
    NullDialogueIntentAdapter,
    OpenAIDialogueIntentAdapter,
    build_dialogue_intent_context,
)
from vampire_storyteller.conversation_context import DialogueHistoryEntry
from vampire_storyteller.game_session import GameSession
from vampire_storyteller.models import NPC
from vampire_storyteller.sample_world import build_sample_world


class DialogueIntentAdapterTests(unittest.TestCase):
    def test_valid_adapter_output_is_accepted_and_threaded_into_dialogue_path(self) -> None:
        world = build_sample_world()
        mock_client = Mock()
        mock_client.responses.create.return_value.output_text = (
            '{"dialogue_act":"ask","dialogue_move":"continue","target_npc_text":"Jonas Reed","topic":"dock","tone":"careful"}'
        )
        adapter = OpenAIDialogueIntentAdapter(api_key="test-key", model="gpt-4.1-mini", client=mock_client)
        context = build_dialogue_intent_context(world, "We need to talk about the dock.")

        proposal = adapter.propose_dialogue_intent(context)

        self.assertIsNotNone(proposal)
        assert proposal is not None
        self.assertEqual(proposal.dialogue_act, "ask")
        self.assertEqual(proposal.dialogue_move, "continue")
        self.assertEqual(proposal.target_npc_text, "Jonas Reed")
        self.assertEqual(proposal.topic, "dock")
        self.assertEqual(proposal.tone, "careful")

        mock_client.responses.create.assert_called_once()
        prompt = mock_client.responses.create.call_args.kwargs["input"]
        self.assertIn("Use only the supplied JSON context as source of truth.", prompt)
        self.assertIn("Use conversation_memory.recent_dialogue_history for immediate continuity", prompt)
        self.assertIn("conversation_memory.previous_interactions_summary for longer-term tone", prompt)
        self.assertIn("Use npc_dossier.personality_guidance only to understand", prompt)
        self.assertIn("Personality guidance must not authorize facts", prompt)
        self.assertIn('"personality_guidance":', prompt)
        self.assertIn('"previous_interactions_summary":"', prompt)
        self.assertIn('"recent_dialogue_history":[', prompt)
        self.assertIn("Quite busy... with a job I want no part of", prompt)
        self.assertIn("But I need your help", prompt)
        self.assertIn("Listen I don't have time for this. What do you know", prompt)
        self.assertIn("A lot, as always. But I am not here to chitty chat. I need info", prompt)

    def test_adapter_repairs_weak_move_and_empty_target_into_usable_dialogue(self) -> None:
        mock_client = Mock()
        mock_client.responses.create.return_value.output_text = (
            '```json\n{"dialogue_act":"ask","dialogue_move":"none","target_npc_text":"","topic":"","tone":""}\n```'
        )
        adapter = OpenAIDialogueIntentAdapter(api_key="test-key", model="gpt-4.1-mini", client=mock_client)
        context = build_dialogue_intent_context(
            build_sample_world(),
            "But I need your help.",
            conversation_focus_npc_id="npc_1",
        )

        proposal = adapter.propose_dialogue_intent(context)

        self.assertIsNotNone(proposal)
        assert proposal is not None
        self.assertEqual(proposal.dialogue_act, "ask")
        self.assertEqual(proposal.dialogue_move, "continue")
        self.assertEqual(proposal.target_npc_text, "Jonas Reed")
        self.assertEqual(proposal.topic, "conversation")
        self.assertEqual(proposal.tone, "curious")

        class StaticDialogueIntentAdapter:
            def propose_dialogue_intent(self, context: DialogueIntentContext) -> DialogueIntentProposal | None:
                return DialogueIntentProposal(
                    dialogue_act="ask",
                    dialogue_move="continue",
                    target_npc_text="Jonas Reed",
                    topic="dock",
                    tone="careful",
                )

        session = GameSession(dialogue_intent_adapter=StaticDialogueIntentAdapter())
        session.process_input("/talk with Jonas")
        result = session.process_input("We need to talk about the dock.")
        interpreted = session.get_last_interpreted_input()

        self.assertIn("dock", result.output_text.lower())
        self.assertIsNotNone(result.dialogue_presentation)
        assert result.dialogue_presentation is not None
        self.assertEqual(result.dialogue_presentation.npc_display_name, "Jonas Reed")
        self.assertIsNotNone(interpreted)
        assert interpreted is not None
        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertIsNotNone(interpreted.dialogue_metadata)
        assert interpreted.dialogue_metadata is not None
        self.assertIn(interpreted.dialogue_metadata.dialogue_act, {DialogueAct.ASK, DialogueAct.UNKNOWN})

    def test_dialogue_intent_context_includes_jonas_memory_layer(self) -> None:
        world = build_sample_world()
        world.npcs["npc_1"].previous_interactions_summary = "Mara already asked Jonas about the dock once."

        context = build_dialogue_intent_context(
            world,
            "Jonas, what happened at the dock?",
            conversation_focus_npc_id="npc_1",
            recent_dialogue_history=(
                DialogueHistoryEntry(speaker="player", utterance_text="Hello Jonas."),
                DialogueHistoryEntry(speaker="Jonas Reed", utterance_text="Evening."),
            ),
        )

        self.assertIsNotNone(context.npc_dossier)
        assert context.npc_dossier is not None
        self.assertEqual(context.npc_dossier.public_persona, "a wary neighborhood informant who keeps public conversations short")
        self.assertIn("terse", context.npc_dossier.personality_guidance.speech_style)
        self.assertIn("indirect", context.npc_dossier.personality_guidance.directness_preference)
        self.assertEqual(context.conversation_memory.previous_interactions_summary, "Mara already asked Jonas about the dock once.")
        self.assertEqual(
            context.conversation_memory.recent_dialogue_history,
            (
                DialogueHistoryEntry(speaker="player", utterance_text="Hello Jonas."),
                DialogueHistoryEntry(speaker="Jonas Reed", utterance_text="Evening."),
            ),
        )

    def test_openai_adapter_on_single_present_npc_falls_back_from_bad_target_text(self) -> None:
        for target_text, raw_input in (
            ("dock", "We need to talk about the dock."),
            ("ledger", "We need to talk about the ledger."),
        ):
            with self.subTest(target_text=target_text):
                mock_client = Mock()
                mock_client.responses.create.return_value.output_text = (
                    '{"dialogue_act":"ask","dialogue_move":"continue","target_npc_text":"'
                    + target_text
                    + '","topic":"dock","tone":"careful"}'
                )
                adapter = OpenAIDialogueIntentAdapter(
                    api_key="test-key",
                    model="gpt-4.1-mini",
                    client=mock_client,
                )
                session = GameSession(dialogue_intent_adapter=adapter)

                session.process_input("/talk with Jonas")
                result = session.process_input(raw_input)
                interpreted = session.get_last_interpreted_input()

                self.assertTrue(result.output_text.strip())
                self.assertIsNotNone(result.dialogue_presentation)
                assert result.dialogue_presentation is not None
                self.assertEqual(result.dialogue_presentation.npc_display_name, "Jonas Reed")
                self.assertIsNotNone(interpreted)
                assert interpreted is not None
                self.assertEqual(interpreted.target_reference, "npc_1")
                self.assertEqual(interpreted.canonical_command, "talk npc_1")
                self.assertIsNotNone(interpreted.dialogue_metadata)
                assert interpreted.dialogue_metadata is not None
                self.assertIn(interpreted.dialogue_metadata.dialogue_act, {DialogueAct.ASK, DialogueAct.UNKNOWN})

    def test_openai_adapter_bad_target_text_does_not_guess_in_multi_npc_scene(self) -> None:
        mock_client = Mock()
        mock_client.responses.create.return_value.output_text = (
            '{"dialogue_act":"ask","dialogue_move":"continue","target_npc_text":"dock","topic":"dock","tone":"careful"}'
        )
        adapter = OpenAIDialogueIntentAdapter(api_key="test-key", model="gpt-4.1-mini", client=mock_client)
        world = build_sample_world()
        world.npcs["npc_3"] = NPC(
            id="npc_3",
            name="Elena Vale",
            role="Observer",
            location_id="loc_cafe",
            attitude_to_player="wary",
            trust_level=0,
            consumed_dialogue_hooks=[],
            goals=[],
            investigation_hint="",
            schedule={},
            traits={},
        )

        from vampire_storyteller.input_interpreter import InputInterpreter

        result = InputInterpreter().interpret(
            "We need to talk about the dock.",
            world,
            dialogue_intent_adapter=adapter,
        )

        self.assertFalse(result.fallback_to_parser)
        self.assertIsNone(result.canonical_command)
        self.assertIsNotNone(result.failure_reason)
        self.assertIn("could not identify", result.failure_reason or "")

    def test_openai_adapter_explicit_absent_npc_still_blocks_safely(self) -> None:
        mock_client = Mock()
        mock_client.responses.create.return_value.output_text = (
            '{"dialogue_act":"ask","dialogue_move":"continue","target_npc_text":"dock","topic":"dock","tone":"careful"}'
        )
        adapter = OpenAIDialogueIntentAdapter(api_key="test-key", model="gpt-4.1-mini", client=mock_client)
        session = GameSession(dialogue_intent_adapter=adapter)

        result = session.process_input("/talk with Elena")

        self.assertIn("Unknown command", result.output_text)
        self.assertFalse(result.render_scene)

    def test_openai_adapter_explicit_present_named_target_still_works(self) -> None:
        mock_client = Mock()
        mock_client.responses.create.return_value.output_text = (
            '{"dialogue_act":"ask","dialogue_move":"continue","target_npc_text":"dock","topic":"dock","tone":"careful"}'
        )
        adapter = OpenAIDialogueIntentAdapter(api_key="test-key", model="gpt-4.1-mini", client=mock_client)
        session = GameSession(dialogue_intent_adapter=adapter)

        session.process_input("/talk with Jonas")
        result = session.process_input("I say to Jonas that we need to talk about the dock.")
        interpreted = session.get_last_interpreted_input()

        self.assertIn("dock", result.output_text.lower())
        self.assertIsNotNone(result.dialogue_presentation)
        assert result.dialogue_presentation is not None
        self.assertEqual(result.dialogue_presentation.npc_display_name, "Jonas Reed")
        self.assertIsNotNone(interpreted)
        assert interpreted is not None
        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertEqual(interpreted.canonical_command, "talk npc_1")

    def test_invalid_enum_values_are_rejected_safely(self) -> None:
        mock_client = Mock()
        mock_client.responses.create.return_value.output_text = (
            '{"dialogue_act":"dance","dialogue_move":"continue","target_npc_text":"Jonas Reed","topic":"dock","tone":"careful"}'
        )
        adapter = OpenAIDialogueIntentAdapter(api_key="test-key", model="gpt-4.1-mini", client=mock_client)
        context = build_dialogue_intent_context(build_sample_world(), "We need to talk about the dock.")

        proposal = adapter.propose_dialogue_intent(context)

        self.assertIsNone(proposal)

    def test_malformed_partial_adapter_output_falls_back_safely(self) -> None:
        mock_client = Mock()
        mock_client.responses.create.return_value.output_text = '{"dialogue_act":"ask","dialogue_move":"continue"}'
        adapter = OpenAIDialogueIntentAdapter(api_key="test-key", model="gpt-4.1-mini", client=mock_client)
        context = build_dialogue_intent_context(build_sample_world(), "Can I ask Sister Eliza something?")

        proposal = adapter.propose_dialogue_intent(context)

        self.assertIsNone(proposal)

    def test_unavailable_adapter_falls_back_to_active_conversation_dialogue(self) -> None:
        session = GameSession(dialogue_intent_adapter=NullDialogueIntentAdapter())

        session.process_input("/talk with Jonas")
        result = session.process_input("I turn back to her and continue.")
        interpreted = session.get_last_interpreted_input()

        self.assertNotIn("Talk is blocked", result.output_text)
        self.assertTrue(result.output_text.strip())
        self.assertIsNotNone(result.dialogue_presentation)
        self.assertIsNotNone(interpreted)
        assert interpreted is not None
        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertEqual(interpreted.canonical_command, "talk npc_1")
        self.assertIsNone(interpreted.failure_reason)

    def test_adapter_cannot_mutate_world_state_by_itself(self) -> None:
        context = build_dialogue_intent_context(build_sample_world(), "We need to talk about the dock.")

        self.assertIsInstance(context, DialogueIntentContext)
        self.assertFalse(hasattr(context, "world_state"))
        self.assertFalse(hasattr(context, "npcs"))
        with self.assertRaises((AttributeError, TypeError)):
            context.player_location_id = "loc_dock"


if __name__ == "__main__":
    unittest.main()
