from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from vampire_storyteller.config import AppConfig
from vampire_storyteller.cli import build_scene_provider
from vampire_storyteller.context_builder import build_scene_snapshot, snapshot_to_footer_text
from vampire_storyteller.narrative_provider import DeterministicSceneNarrativeProvider
from vampire_storyteller.openai_narrative_provider import OpenAISceneNarrativeProvider
from vampire_storyteller.game_session import GameSession
from vampire_storyteller.sample_world import build_sample_world
from vampire_storyteller.world_state import WorldState


class FailingSceneProvider:
    def render_scene(self, world_state: WorldState) -> str:
        raise RuntimeError("provider failed")


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

    def test_session_uses_deterministic_provider_when_openai_not_selected(self) -> None:
        provider, notice = build_scene_provider(
            AppConfig(
                openai_api_key=None,
                openai_model="gpt-4.1-mini",
                use_openai_scene_provider=False,
            )
        )

        self.assertIsInstance(provider, DeterministicSceneNarrativeProvider)
        self.assertIsNone(notice)

    def test_missing_api_key_with_opt_in_flag_falls_back_safely(self) -> None:
        provider, notice = build_scene_provider(
            AppConfig(
                openai_api_key=None,
                openai_model="gpt-4.1-mini",
                use_openai_scene_provider=True,
            )
        )

        self.assertIsInstance(provider, DeterministicSceneNarrativeProvider)
        self.assertIsNotNone(notice)
        self.assertIn("OPENAI_API_KEY is missing", notice)

    def test_shared_provider_helper_uses_openai_model_from_runtime_config(self) -> None:
        with patch("vampire_storyteller.cli.OpenAISceneNarrativeProvider") as mock_provider_ctor:
            provider, notice = build_scene_provider(
                AppConfig(
                    openai_api_key="test-key",
                    openai_model="gpt-4.1-mini",
                    use_openai_scene_provider=True,
                )
            )

        self.assertIsNone(notice)
        mock_provider_ctor.assert_called_once_with(api_key="test-key", model="gpt-4.1-mini")
        self.assertIs(provider, mock_provider_ctor.return_value)

    def test_provider_render_failure_falls_back_safely(self) -> None:
        session = GameSession(scene_provider=FailingSceneProvider())

        startup_text = session.get_startup_text()
        look_result = session.process_input("look")

        self.assertIn("Time: 2026-04-09T22:00:00+02:00", startup_text)
        self.assertIn("NPCs Present: Jonas Reed (Informant, attitude: wary, trust: 0)", startup_text)
        self.assertIn("Time: 2026-04-09T22:00:00+02:00", look_result.output_text)

    def test_deterministic_provider_behavior_remains_unchanged(self) -> None:
        world = build_sample_world()
        provider = DeterministicSceneNarrativeProvider()

        self.assertEqual(provider.render_scene(world), provider.render_scene(world))
        self.assertNotIn("---", provider.render_scene(world))


if __name__ == "__main__":
    unittest.main()
