from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from vampire_storyteller.cli import _build_cli_prompt, _build_runtime_banner, _format_cli_result, build_runtime_composition
from vampire_storyteller.command_result import CommandResult, DialoguePresentation
from vampire_storyteller.config import AppConfig, load_config
from vampire_storyteller.game_session import GameSession


class CliTranscriptTests(unittest.TestCase):
    def test_prompt_defaults_without_active_conversation(self) -> None:
        session = GameSession()

        self.assertEqual(_build_cli_prompt(session), "Action > ")

    def test_prompt_uses_player_prompt_during_active_conversation(self) -> None:
        session = GameSession()

        session.process_input("/talk with Jonas, hello")

        self.assertEqual(_build_cli_prompt(session), "Player > ")

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

    def test_transcript_format_keeps_consistent_player_and_npc_labels(self) -> None:
        formatted = _format_cli_result(
            CommandResult(
                output_text="Evening.",
                dialogue_presentation=DialoguePresentation(
                    player_utterance="Hello Jonas",
                    npc_display_name="Jonas Reed",
                    focus_changed=True,
                ),
            )
        )

        self.assertIn('Conversation: Jonas Reed', formatted)
        self.assertIn('Player: "Hello Jonas"', formatted)
        self.assertIn('Jonas Reed: "Evening."', formatted)

    def test_full_openai_storyteller_mode_uses_openai_components(self) -> None:
        with patch("vampire_storyteller.cli.OpenAISceneNarrativeProvider") as mock_scene_ctor:
            with patch("vampire_storyteller.cli.OpenAIDialogueIntentAdapter") as mock_intent_ctor:
                with patch("vampire_storyteller.cli.OpenAIDialogueRenderer") as mock_renderer_ctor:
                    runtime = build_runtime_composition(
                        AppConfig(
                            openai_api_key="test-key",
                            openai_model="gpt-4.1-mini",
                            command_prefix="/",
                        )
                    )

        self.assertTrue(runtime.full_openai_storyteller_mode)
        self.assertEqual(runtime.mode_label, "OpenAI storyteller")
        self.assertEqual(runtime.scene_label, "OpenAI")
        self.assertEqual(runtime.dialogue_intent_label, "OpenAI")
        self.assertEqual(runtime.dialogue_render_label, "OpenAI")
        mock_scene_ctor.assert_called_once_with(api_key="test-key", model="gpt-4.1-mini")
        mock_intent_ctor.assert_called_once_with(api_key="test-key", model="gpt-4.1-mini")
        mock_renderer_ctor.assert_called_once_with(api_key="test-key", model="gpt-4.1-mini")

        banner = _build_runtime_banner(
            AppConfig(
                openai_api_key="test-key",
                openai_model="gpt-4.1-mini",
                command_prefix="/",
            ),
            runtime,
        )

        self.assertIn("Mode: OpenAI storyteller", banner)
        self.assertIn("Scene narration: OpenAI", banner)
        self.assertIn("Dialogue intent: OpenAI", banner)
        self.assertIn("Dialogue rendering: OpenAI", banner)
        self.assertIn("Command prefix: /", banner)
        self.assertIn("Preset: openai_storyteller only", banner)
        self.assertNotIn("mixed", banner.lower())
        self.assertNotIn("deterministic", banner.lower())

    def test_run_cli_passes_command_prefix_to_game_session(self) -> None:
        runtime = Mock(
            scene_provider=Mock(),
            dialogue_intent_adapter=Mock(),
            dialogue_renderer=Mock(),
            mode_label="OpenAI storyteller",
            scene_label="OpenAI",
            dialogue_intent_label="OpenAI",
            dialogue_render_label="OpenAI",
            notices=(),
            full_openai_storyteller_mode=True,
        )
        session = Mock()
        session.get_conversation_focus_npc_id.return_value = None
        session.get_startup_text.return_value = "startup"

        with patch("vampire_storyteller.cli.load_config", return_value=AppConfig(openai_api_key=None, openai_model="gpt-4.1-mini", command_prefix="\\")):
            with patch("vampire_storyteller.cli.build_runtime_composition", return_value=runtime):
                with patch("vampire_storyteller.cli.GameSession", return_value=session) as mock_session_ctor:
                    with patch("vampire_storyteller.cli.input", side_effect=EOFError):
                        with patch("vampire_storyteller.cli.print"):
                            from vampire_storyteller.cli import run_cli

                            run_cli()

        mock_session_ctor.assert_called_once_with(
            scene_provider=runtime.scene_provider,
            dialogue_intent_adapter=runtime.dialogue_intent_adapter,
            dialogue_renderer=runtime.dialogue_renderer,
            command_prefix="\\",
        )

    def test_load_config_reads_openai_model(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "app_config.json"
            config_path.write_text('{"openai_model": "gpt-4.1"}', encoding="utf-8")

            config = load_config(config_path=config_path, local_config_path=Path(temp_dir) / "missing.local.json", dotenv_path=Path(temp_dir) / ".env")

        self.assertEqual(config.openai_model, "gpt-4.1")

    def test_missing_api_key_with_runtime_build_fails_loudly(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "requires OPENAI_API_KEY"):
            build_runtime_composition(
                AppConfig(
                    openai_api_key=None,
                    openai_model="gpt-4.1-mini",
                )
            )


if __name__ == "__main__":
    unittest.main()
