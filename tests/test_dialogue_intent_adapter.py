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
from vampire_storyteller.game_session import GameSession
from vampire_storyteller.models import NPC
from vampire_storyteller.sample_world import build_sample_world


class DialogueIntentAdapterTests(unittest.TestCase):
    def test_valid_adapter_output_is_accepted_and_threaded_into_dialogue_path(self) -> None:
        world = build_sample_world()
        mock_client = Mock()
        mock_client.responses.create.return_value.output_text = (
            '{"dialogue_act":"ask","target_npc_text":"Jonas Reed","topic":"dock","tone":"careful"}'
        )
        adapter = OpenAIDialogueIntentAdapter(api_key="test-key", model="gpt-4.1-mini", client=mock_client)
        context = build_dialogue_intent_context(world, "We need to talk about the dock.")

        proposal = adapter.propose_dialogue_intent(context)

        self.assertIsNotNone(proposal)
        assert proposal is not None
        self.assertEqual(proposal.dialogue_act, "ask")
        self.assertEqual(proposal.target_npc_text, "Jonas Reed")
        self.assertEqual(proposal.topic, "dock")
        self.assertEqual(proposal.tone, "careful")

        class StaticDialogueIntentAdapter:
            def propose_dialogue_intent(self, context: DialogueIntentContext) -> DialogueIntentProposal | None:
                return DialogueIntentProposal(
                    dialogue_act="ask",
                    target_npc_text="Jonas Reed",
                    topic="dock",
                    tone="careful",
                )

        session = GameSession(dialogue_intent_adapter=StaticDialogueIntentAdapter())
        result = session.process_input("We need to talk about the dock.")
        interpreted = session.get_last_interpreted_input()

        self.assertIn("Jonas Reed", result.output_text)
        self.assertIsNotNone(interpreted)
        assert interpreted is not None
        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertEqual(interpreted.dialogue_metadata.topic, "dock")
        self.assertEqual(interpreted.dialogue_metadata.tone, "careful")
        self.assertEqual(interpreted.dialogue_metadata.dialogue_act, DialogueAct.ASK)

    def test_adapter_on_single_present_npc_grounds_implicit_dialogue_line(self) -> None:
        class ImplicitDialogueIntentAdapter:
            def propose_dialogue_intent(self, context: DialogueIntentContext) -> DialogueIntentProposal | None:
                return DialogueIntentProposal(
                    dialogue_act="ask",
                    target_npc_text="",
                    topic="dock",
                    tone="careful",
                )

        session = GameSession(dialogue_intent_adapter=ImplicitDialogueIntentAdapter())

        result = session.process_input("We need to talk about the dock.")
        interpreted = session.get_last_interpreted_input()

        self.assertIn("Jonas Reed", result.output_text)
        self.assertIsNotNone(interpreted)
        assert interpreted is not None
        self.assertEqual(interpreted.target_reference, "npc_1")
        self.assertEqual(interpreted.canonical_command, "talk npc_1")
        self.assertEqual(interpreted.dialogue_metadata.dialogue_act, DialogueAct.ASK)
        self.assertEqual(interpreted.dialogue_metadata.topic, "dock")
        self.assertEqual(interpreted.dialogue_metadata.tone, "careful")

    def test_adapter_on_multiple_present_npcs_does_not_guess_implicit_target(self) -> None:
        class ImplicitDialogueIntentAdapter:
            def propose_dialogue_intent(self, context: DialogueIntentContext) -> DialogueIntentProposal | None:
                return DialogueIntentProposal(
                    dialogue_act="ask",
                    target_npc_text="her",
                    topic="dock",
                    tone="careful",
                )

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
            dialogue_intent_adapter=ImplicitDialogueIntentAdapter(),
        )

        self.assertFalse(result.fallback_to_parser)
        self.assertIsNone(result.canonical_command)
        self.assertIsNotNone(result.failure_reason)
        self.assertIn("could not identify", result.failure_reason or "")

    def test_adapter_on_explicit_absent_npc_still_blocks_safely(self) -> None:
        class ExplicitAbsentDialogueIntentAdapter:
            def propose_dialogue_intent(self, context: DialogueIntentContext) -> DialogueIntentProposal | None:
                return DialogueIntentProposal(
                    dialogue_act="ask",
                    target_npc_text="Sister Eliza",
                    topic="dock",
                    tone="careful",
                )

        session = GameSession(dialogue_intent_adapter=ExplicitAbsentDialogueIntentAdapter())

        result = session.process_input("Sister Eliza, we need to speak.")

        self.assertIn("Talk is blocked", result.output_text)
        self.assertIn("not present at Blackthorn Cafe", result.output_text)
        self.assertFalse(result.render_scene)

    def test_invalid_enum_values_are_rejected_safely(self) -> None:
        mock_client = Mock()
        mock_client.responses.create.return_value.output_text = (
            '{"dialogue_act":"dance","target_npc_text":"Jonas Reed","topic":"dock","tone":"careful"}'
        )
        adapter = OpenAIDialogueIntentAdapter(api_key="test-key", model="gpt-4.1-mini", client=mock_client)
        context = build_dialogue_intent_context(build_sample_world(), "We need to talk about the dock.")

        proposal = adapter.propose_dialogue_intent(context)

        self.assertIsNone(proposal)

    def test_malformed_partial_adapter_output_falls_back_safely(self) -> None:
        mock_client = Mock()
        mock_client.responses.create.return_value.output_text = '{"dialogue_act":"ask"}'
        adapter = OpenAIDialogueIntentAdapter(api_key="test-key", model="gpt-4.1-mini", client=mock_client)
        context = build_dialogue_intent_context(build_sample_world(), "Can I ask Sister Eliza something?")

        proposal = adapter.propose_dialogue_intent(context)

        self.assertIsNone(proposal)

    def test_unavailable_adapter_falls_back_to_deterministic_behavior(self) -> None:
        session = GameSession(dialogue_intent_adapter=NullDialogueIntentAdapter())

        session.process_input("Jonas, good evening.")
        result = session.process_input("I turn back to her and continue.")

        self.assertIn("Jonas Reed", result.output_text)
        self.assertEqual(session.get_last_interpreted_input().target_reference, "npc_1")
        self.assertEqual(session.get_last_interpreted_input().dialogue_metadata.dialogue_act, DialogueAct.UNKNOWN)

    def test_adapter_cannot_mutate_world_state_by_itself(self) -> None:
        context = build_dialogue_intent_context(build_sample_world(), "We need to talk about the dock.")

        self.assertIsInstance(context, DialogueIntentContext)
        self.assertFalse(hasattr(context, "world_state"))
        self.assertFalse(hasattr(context, "npcs"))
        with self.assertRaises((AttributeError, TypeError)):
            context.player_location_id = "loc_dock"


if __name__ == "__main__":
    unittest.main()
