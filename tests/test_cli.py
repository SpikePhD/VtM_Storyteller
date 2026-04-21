from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from vampire_storyteller.cli import _build_cli_prompt, _build_runtime_banner, _format_cli_result, build_runtime_composition
from vampire_storyteller.config import AppConfig, load_config
from vampire_storyteller.command_result import CommandResult, DialoguePresentation
from vampire_storyteller.game_session import GameSession
from vampire_storyteller.narrative_provider import DeterministicSceneNarrativeProvider


class CliTranscriptTests(unittest.TestCase):
    def test_prompt_defaults_without_active_conversation(self) -> None:
        session = GameSession()

        self.assertEqual(_build_cli_prompt(session), "> ")

    def test_prompt_uses_focused_npc_name(self) -> None:
        session = GameSession()
        session.process_input("Jonas, hello")

        self.assertEqual(_build_cli_prompt(session), "Jonas > ")

    def test_prompt_resets_after_focus_clears(self) -> None:
        session = GameSession()
        session.process_input("Jonas, hello")
        session.process_input("move loc_church")

        self.assertEqual(_build_cli_prompt(session), "> ")

    def test_transcript_format_adds_banner_on_focus_change(self) -> None:
        formatted = _format_cli_result(
            CommandResult(
                output_text="I'm holding up. You needed something specific?",
                dialogue_presentation=DialoguePresentation(
                    player_utterance="How are you?",
                    npc_display_name="Jonas Reed",
                    focus_changed=True,
                ),
            )
        )

        self.assertEqual(
            formatted,
            'Conversation: Jonas Reed\nPlayer: "How are you?"\nJonas Reed: "I\'m holding up. You needed something specific?"',
        )

    def test_transcript_format_skips_banner_when_focus_does_not_change(self) -> None:
        formatted = _format_cli_result(
            CommandResult(
                output_text="North Dockside. That's where the paper trail begins.",
                dialogue_presentation=DialoguePresentation(
                    player_utterance="What happened at the dock?",
                    npc_display_name="Jonas Reed",
                    focus_changed=False,
                ),
            )
        )

        self.assertEqual(
            formatted,
            'Player: "What happened at the dock?"\nJonas Reed: "North Dockside. That\'s where the paper trail begins."',
        )

    def test_non_dialogue_result_stays_plain(self) -> None:
        self.assertEqual(_format_cli_result(CommandResult(output_text="Unsupported freeform input.")), "Unsupported freeform input.")

    def test_full_openai_storyteller_mode_uses_all_openai_components(self) -> None:
        with patch("vampire_storyteller.cli.OpenAISceneNarrativeProvider") as mock_scene_ctor:
            with patch("vampire_storyteller.cli.OpenAIDialogueIntentAdapter") as mock_intent_ctor:
                with patch("vampire_storyteller.cli.OpenAIDialogueRenderer") as mock_renderer_ctor:
                    runtime = build_runtime_composition(
                        AppConfig(
                            openai_api_key="test-key",
                            openai_model="gpt-4.1-mini",
                            use_openai_scene_provider=False,
                            use_openai_dialogue_intent_adapter=False,
                            use_openai_dialogue_renderer=False,
                            use_openai_storyteller_mode=True,
                        )
                    )

        self.assertTrue(runtime.full_openai_storyteller_mode)
        self.assertEqual(runtime.mode_label, "OpenAI storyteller")
        self.assertEqual(runtime.scene_label, "OpenAI")
        self.assertEqual(runtime.dialogue_intent_label, "OpenAI")
        self.assertEqual(runtime.dialogue_render_label, "OpenAI")
        self.assertEqual(runtime.notices, ())
        mock_scene_ctor.assert_called_once_with(api_key="test-key", model="gpt-4.1-mini")
        mock_intent_ctor.assert_called_once_with(api_key="test-key", model="gpt-4.1-mini")
        mock_renderer_ctor.assert_called_once_with(api_key="test-key", model="gpt-4.1-mini")

        banner = _build_runtime_banner(
            AppConfig(
                openai_api_key="test-key",
                openai_model="gpt-4.1-mini",
                use_openai_scene_provider=False,
                use_openai_dialogue_intent_adapter=False,
                use_openai_dialogue_renderer=False,
                use_openai_storyteller_mode=True,
            ),
            runtime,
        )

        self.assertIn("Mode: OpenAI storyteller", banner)
        self.assertIn("Scene narration: OpenAI", banner)
        self.assertIn("Dialogue intent: OpenAI", banner)
        self.assertIn("Dialogue rendering: OpenAI", banner)
        self.assertIn("Storyteller preset: yes", banner)
        self.assertIn("Mixed mode: no", banner)
        self.assertNotIn("deterministic", banner.lower())

    def test_mixed_runtime_is_reported_explicitly_as_mixed(self) -> None:
        runtime = build_runtime_composition(
            AppConfig(
                openai_api_key="test-key",
                openai_model="gpt-4.1-mini",
                use_openai_scene_provider=True,
                use_openai_dialogue_intent_adapter=True,
                use_openai_dialogue_renderer=False,
            )
        )

        banner = _build_runtime_banner(
            AppConfig(
                openai_api_key="test-key",
                openai_model="gpt-4.1-mini",
                use_openai_scene_provider=True,
                use_openai_dialogue_intent_adapter=True,
                use_openai_dialogue_renderer=False,
            ),
            runtime,
        )

        self.assertEqual(runtime.mode_label, "Mixed")
        self.assertIn("Mode: Mixed", banner)
        self.assertIn("Dialogue rendering: deterministic", banner)
        self.assertIn("Mixed mode: yes", banner)

    def test_deterministic_runtime_is_explicit_and_not_a_hidden_fallback(self) -> None:
        runtime = build_runtime_composition(
            AppConfig(
                openai_api_key=None,
                openai_model="gpt-4.1-mini",
                use_openai_scene_provider=False,
                use_openai_dialogue_intent_adapter=False,
                use_openai_dialogue_renderer=False,
                use_openai_storyteller_mode=False,
            )
        )

        banner = _build_runtime_banner(
            AppConfig(
                openai_api_key=None,
                openai_model="gpt-4.1-mini",
                use_openai_scene_provider=False,
                use_openai_dialogue_intent_adapter=False,
                use_openai_dialogue_renderer=False,
                use_openai_storyteller_mode=False,
            ),
            runtime,
        )

        self.assertEqual(runtime.mode_label, "Deterministic")
        self.assertEqual(runtime.scene_label, "deterministic")
        self.assertEqual(runtime.dialogue_intent_label, "deterministic")
        self.assertEqual(runtime.dialogue_render_label, "deterministic")
        self.assertIn("Mode: Deterministic", banner)
        self.assertIn("Dialogue rendering: deterministic", banner)
        self.assertIn("Storyteller preset: no", banner)
        self.assertIn("Mixed mode: no", banner)

    def test_runtime_mode_deterministic_overrides_component_switches(self) -> None:
        runtime = build_runtime_composition(
            AppConfig(
                openai_api_key="test-key",
                openai_model="gpt-4.1-mini",
                use_openai_scene_provider=True,
                use_openai_dialogue_intent_adapter=True,
                use_openai_dialogue_renderer=True,
                runtime_mode="deterministic",
            )
        )

        self.assertEqual(runtime.mode_label, "Deterministic")
        self.assertEqual(runtime.scene_label, "deterministic")
        self.assertEqual(runtime.dialogue_intent_label, "deterministic")
        self.assertEqual(runtime.dialogue_render_label, "deterministic")
        self.assertFalse(runtime.full_openai_storyteller_mode)

    def test_runtime_mode_knob_is_loaded_from_config_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            config_path = temp_root / "app_config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "runtime_mode": "openai_storyteller",
                        "openai_model": "gpt-4.1-mini",
                        "use_openai_scene_provider": False,
                        "use_openai_dialogue_intent_adapter": False,
                        "use_openai_dialogue_renderer": False,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            config = load_config(config_path=config_path, local_config_path=temp_root / "missing.local.json", dotenv_path=temp_root / ".env")

        self.assertEqual(config.runtime_mode, "openai_storyteller")
        self.assertEqual(config.openai_model, "gpt-4.1-mini")
        self.assertFalse(config.use_openai_scene_provider)
        self.assertFalse(config.use_openai_dialogue_intent_adapter)
        self.assertFalse(config.use_openai_dialogue_renderer)

    def test_full_openai_storyteller_mode_without_renderer_availability_fails_loudly(self) -> None:
        with patch("vampire_storyteller.cli.OpenAISceneNarrativeProvider") as mock_scene_ctor:
            with patch("vampire_storyteller.cli.OpenAIDialogueIntentAdapter") as mock_intent_ctor:
                with patch("vampire_storyteller.cli.OpenAIDialogueRenderer", side_effect=RuntimeError("renderer failed")):
                    with self.assertRaisesRegex(RuntimeError, "Full OpenAI storyteller mode failed to initialize"):
                        build_runtime_composition(
                            AppConfig(
                                openai_api_key="test-key",
                                openai_model="gpt-4.1-mini",
                                use_openai_scene_provider=False,
                                use_openai_dialogue_intent_adapter=False,
                                use_openai_dialogue_renderer=False,
                                use_openai_storyteller_mode=True,
                            )
                        )

        mock_scene_ctor.assert_called_once_with(api_key="test-key", model="gpt-4.1-mini")
        mock_intent_ctor.assert_called_once_with(api_key="test-key", model="gpt-4.1-mini")


if __name__ == "__main__":
    unittest.main()
