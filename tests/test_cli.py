from __future__ import annotations

import unittest

from vampire_storyteller.cli import _build_cli_prompt, _build_runtime_banner, _format_cli_result
from vampire_storyteller.config import AppConfig
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

    def test_runtime_banner_marks_openai_dialogue_rendering_as_mandatory(self) -> None:
        banner = _build_runtime_banner(
            AppConfig(
                openai_api_key="test-key",
                openai_model="gpt-4.1-mini",
                use_openai_scene_provider=False,
                use_openai_dialogue_intent_adapter=False,
                use_openai_dialogue_renderer=True,
            ),
            DeterministicSceneNarrativeProvider(),
            object(),
            object(),
            None,
            None,
            "OpenAI dialogue renderer requested but OPENAI_API_KEY is missing; deterministic dialogue rendering is disabled in OpenAI dialogue mode, so dialogue turns will fail explicitly.",
        )

        self.assertIn("Dialogue rendering: OpenAI", banner)
        self.assertIn("Dialogue render fallback: no (disabled by design in OpenAI dialogue mode)", banner)
        self.assertIn("Dialogue render notice:", banner)


if __name__ == "__main__":
    unittest.main()
