from __future__ import annotations

import unittest
from unittest.mock import patch

import vampire_storyteller.gui_app as gui_app
from vampire_storyteller import build_scene_provider, run_cli, run_gui
from vampire_storyteller.command_result import CommandResult
from vampire_storyteller.exceptions import CommandParseError, WorldStateError
from vampire_storyteller.game_session import GameSession
from vampire_storyteller.gui_app import (
    GuiSessionController,
    build_status_panel_data,
    format_status_panel_text,
)
from vampire_storyteller.sample_world import build_sample_world


class FakeSession:
    def __init__(self) -> None:
        self.world_state = build_sample_world()
        self.processed_inputs: list[str] = []
        self.startup_text_value = "startup scene"

    def get_startup_text(self) -> str:
        return self.startup_text_value

    def get_world_state(self):
        return self.world_state

    def process_input(self, raw_input: str) -> CommandResult:
        self.processed_inputs.append(raw_input)
        return CommandResult(output_text=f"processed:{raw_input}", should_quit=raw_input == "quit", render_scene=True)


class RaisingParseSession(FakeSession):
    def process_input(self, raw_input: str) -> CommandResult:
        raise CommandParseError("bad command")


class RaisingActionSession(FakeSession):
    def process_input(self, raw_input: str) -> CommandResult:
        raise WorldStateError("failed action")


class GuiAppTests(unittest.TestCase):
    def test_run_gui_is_exported(self) -> None:
        self.assertTrue(callable(run_gui))

    def test_run_cli_is_exported(self) -> None:
        self.assertTrue(callable(run_cli))

    def test_shared_provider_helper_is_exported(self) -> None:
        self.assertTrue(callable(build_scene_provider))

    def test_status_panel_helper_formats_current_world_state(self) -> None:
        world = build_sample_world()

        data = build_status_panel_data(world)
        text = format_status_panel_text(world)

        self.assertEqual(data.player_name, "Mara Vale")
        self.assertEqual(data.location_name, "Blackthorn Cafe")
        self.assertEqual(data.current_time, "2026-04-09T22:00:00+02:00")
        self.assertIn("Player: Mara Vale", text)
        self.assertIn("Location: Blackthorn Cafe", text)
        self.assertIn("Time: 2026-04-09T22:00:00+02:00", text)

    def test_controller_uses_session_for_startup_status_and_submission(self) -> None:
        session = FakeSession()
        controller = GuiSessionController(session=session)

        self.assertEqual(controller.startup_text(), "startup scene")
        self.assertIn("Player: Mara Vale", controller.status_text())

        outcome = controller.submit_command("look")

        self.assertEqual(session.processed_inputs, ["look"])
        self.assertEqual(outcome.output_text, "processed:look")
        self.assertFalse(outcome.should_quit)

    def test_controller_reports_parse_and_action_errors_user_facing(self) -> None:
        parse_controller = GuiSessionController(session=RaisingParseSession())
        action_controller = GuiSessionController(session=RaisingActionSession())

        self.assertEqual(parse_controller.submit_command("inspect").output_text, "Input error: bad command")
        self.assertEqual(action_controller.submit_command("move loc_church").output_text, "Action failed: failed action")

    def test_controller_prepends_startup_notice_when_provided(self) -> None:
        session = FakeSession()
        controller = GuiSessionController(session=session, startup_notice="OpenAI storyteller startup notice.")

        startup_text = controller.startup_text()

        self.assertTrue(startup_text.startswith("OpenAI storyteller startup notice."))
        self.assertIn("startup scene", startup_text)

    def test_run_gui_uses_shared_provider_selection_path(self) -> None:
        calls: dict[str, object] = {}

        class FakeApp:
            def __init__(self, *args: object, **kwargs: object) -> None:
                calls["app_args"] = args
                calls["app_kwargs"] = kwargs

            @staticmethod
            def instance() -> object | None:
                return None

            def exec(self) -> int:
                calls["exec"] = True
                return 0

        class FakeWindow:
            def __init__(self, *, scene_provider: object | None = None, startup_notice: str | None = None) -> None:
                calls["scene_provider"] = scene_provider
                calls["startup_notice"] = startup_notice

            def show(self) -> None:
                calls["shown"] = True

        fake_provider = object()
        with patch.object(gui_app, "build_scene_provider", return_value=(fake_provider, "notice")):
            with patch.object(gui_app, "QApplication", FakeApp):
                with patch.object(gui_app, "GameWindow", FakeWindow, create=True):
                    gui_app.run_gui()

        self.assertIs(calls["scene_provider"], fake_provider)
        self.assertEqual(calls["startup_notice"], "notice")
        self.assertTrue(calls["shown"])
        self.assertTrue(calls["exec"])

    def test_help_text_includes_investigate(self) -> None:
        from vampire_storyteller.text_renderers import render_help_text

        self.assertIn("investigate", render_help_text())


if __name__ == "__main__":
    unittest.main()
