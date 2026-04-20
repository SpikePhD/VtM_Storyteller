from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from vampire_storyteller.cli import build_dialogue_renderer
from vampire_storyteller.config import AppConfig
from vampire_storyteller.dialogue_renderer import DialogueRenderInput
from vampire_storyteller.openai_dialogue_renderer import OpenAIDialogueRenderer


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
                dialogue_domain="lead_topic",
                topic_status="productive",
                adjudication_resolution_kind="allowed",
                conversation_stance="neutral",
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
            )
        )

        self.assertEqual(output, "Storyteller dialogue text.")
        called_kwargs = mock_client.responses.create.call_args.kwargs
        self.assertEqual(called_kwargs["model"], "gpt-4.1-mini")
        prompt = called_kwargs["input"]
        self.assertIn("Use only the supplied JSON payload as source of truth.", prompt)
        self.assertIn("Do not invent clue state, plot advancement, trust changes, NPC presence, permissions, legality, or check outcomes.", prompt)
        self.assertIn('"npc_name":"Jonas Reed"', prompt)
        self.assertIn('"dialogue_domain":"lead_topic"', prompt)
        self.assertIn('"plot_name":"Missing Ledger"', prompt)

    def test_shared_dialogue_renderer_helper_uses_openai_model_from_runtime_config(self) -> None:
        with patch("vampire_storyteller.cli.OpenAIDialogueRenderer") as mock_renderer_ctor:
            renderer, notice = build_dialogue_renderer(
                AppConfig(
                    openai_api_key="test-key",
                    openai_model="gpt-4.1-mini",
                    use_openai_scene_provider=False,
                    use_openai_dialogue_intent_adapter=False,
                    use_openai_dialogue_renderer=True,
                )
            )

        self.assertIsNone(notice)
        mock_renderer_ctor.assert_called_once_with(api_key="test-key", model="gpt-4.1-mini")
        self.assertIs(renderer, mock_renderer_ctor.return_value)


if __name__ == "__main__":
    unittest.main()
