from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from vampire_storyteller.cli import build_dialogue_intent_adapter, build_scene_provider
from vampire_storyteller.config import AppConfig
from vampire_storyteller.context_builder import build_scene_snapshot, snapshot_to_footer_text
from vampire_storyteller.openai_narrative_provider import OpenAISceneNarrativeProvider
from vampire_storyteller.sample_world import build_sample_world


class OpenAINarrativeProviderTests(unittest.TestCase):
    def test_provider_can_be_constructed_with_mock_client(self) -> None:
        mock_client = Mock()
        provider = OpenAISceneNarrativeProvider(api_key="test-key", model="gpt-4.1-mini", client=mock_client)

        self.assertIsNotNone(provider)

    def test_provider_builds_grounded_output_from_snapshot_input(self) -> None:
        world = build_sample_world()
        mock_client = Mock()
        mock_client.responses.create.return_value.output_text = "Atmospheric scene text."
        provider = OpenAISceneNarrativeProvider(api_key="test-key", model="gpt-4.1-mini", client=mock_client)

        output = provider.render_scene(world)

        self.assertTrue(output.startswith("Atmospheric scene text."))
        self.assertIn("\n\n---\n", output)
        mock_client.responses.create.assert_called_once()
        called_kwargs = mock_client.responses.create.call_args.kwargs
        self.assertEqual(called_kwargs["model"], "gpt-4.1-mini")
        prompt = called_kwargs["input"]
        self.assertIn("Use only the supplied JSON snapshot as source of truth.", prompt)
        self.assertIn("Do not invent weather, sounds, architecture, room details, crowd details, lighting, smells, motion, or emotional beats unless explicitly present in the snapshot.", prompt)
        self.assertIn("Do not invent new exits, entities, plot stages, or recent events.", prompt)
        self.assertIn("Do not contradict NPC presence or absence.", prompt)
        self.assertIn('"npcs_present"', prompt)
        self.assertIn('"exits"', prompt)
        self.assertIn('"location_name":"Blackthorn Cafe"', prompt)
        self.assertIn('"location_scene_hook":"Muted conversations and posted notices make the cafe a quiet place to ask questions."', prompt)
        self.assertIn('"location_notable_features":["corner booths","notice board","narrow back room"]', prompt)
        self.assertIn('"location_flavor_tags":["quiet","watchful","public"]', prompt)
        self.assertIn('"name":"Jonas Reed"', prompt)
        self.assertNotIn('"location_type"', prompt)
        self.assertNotIn('"location_danger_level"', prompt)

    def test_provider_appends_deterministic_footer(self) -> None:
        world = build_sample_world()
        mock_client = Mock()
        mock_client.responses.create.return_value.output_text = "Atmospheric scene text."
        provider = OpenAISceneNarrativeProvider(api_key="test-key", model="gpt-4.1-mini", client=mock_client)

        output = provider.render_scene(world)
        footer = snapshot_to_footer_text(build_scene_snapshot(world))

        self.assertTrue(output.startswith("Atmospheric scene text."))
        self.assertIn("\n\n---\n", output)
        self.assertIn(footer, output)
        self.assertIn("Location: Blackthorn Cafe", output)
        self.assertIn("Exits: North Dockside, Saint Judith's Church", output)
        self.assertIn("NPCs Present: Jonas Reed (Informant, trust: 0)", output)
        self.assertIn("Active Plots: Missing Ledger [hook]", output)
        self.assertIn("Recent Events: None", output)

    def test_shared_provider_helper_uses_openai_model_from_runtime_config(self) -> None:
        with patch("vampire_storyteller.cli.OpenAISceneNarrativeProvider") as mock_provider_ctor:
            provider, notice = build_scene_provider(
                AppConfig(
                    openai_api_key="test-key",
                    openai_model="gpt-4.1-mini",
                )
            )

        self.assertIsNone(notice)
        mock_provider_ctor.assert_called_once_with(api_key="test-key", model="gpt-4.1-mini")
        self.assertIs(provider, mock_provider_ctor.return_value)

    def test_shared_provider_helper_requires_an_api_key(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "requires OPENAI_API_KEY"):
            build_scene_provider(
                AppConfig(
                    openai_api_key=None,
                    openai_model="gpt-4.1-mini",
                )
            )

    def test_shared_dialogue_adapter_helper_uses_openai_model_from_runtime_config(self) -> None:
        with patch("vampire_storyteller.cli.OpenAIDialogueIntentAdapter") as mock_adapter_ctor:
            adapter, notice = build_dialogue_intent_adapter(
                AppConfig(
                    openai_api_key="test-key",
                    openai_model="gpt-4.1-mini",
                )
            )

        self.assertIsNone(notice)
        mock_adapter_ctor.assert_called_once_with(api_key="test-key", model="gpt-4.1-mini")
        self.assertIs(adapter, mock_adapter_ctor.return_value)

    def test_shared_dialogue_adapter_helper_requires_an_api_key(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "requires OPENAI_API_KEY"):
            build_dialogue_intent_adapter(
                AppConfig(
                    openai_api_key=None,
                    openai_model="gpt-4.1-mini",
                )
            )


if __name__ == "__main__":
    unittest.main()
