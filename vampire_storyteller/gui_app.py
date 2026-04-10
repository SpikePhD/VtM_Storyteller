from __future__ import annotations

from dataclasses import dataclass
import sys
from typing import Protocol

from .command_result import CommandResult
from .exceptions import CommandParseError, WorldStateError
from .game_session import GameSession
from .cli import build_scene_provider
from .narrative_provider import SceneNarrativeProvider
from .world_state import WorldState

try:  # pragma: no cover - exercised indirectly when Qt is installed
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QApplication,
        QFormLayout,
        QFrame,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QPushButton,
        QPlainTextEdit,
        QVBoxLayout,
        QWidget,
    )
except ImportError:  # pragma: no cover - import guard for environments without Qt
    Qt = None  # type: ignore[assignment]
    QApplication = None  # type: ignore[assignment]
    QFormLayout = None  # type: ignore[assignment]
    QFrame = None  # type: ignore[assignment]
    QGroupBox = None  # type: ignore[assignment]
    QHBoxLayout = None  # type: ignore[assignment]
    QLabel = None  # type: ignore[assignment]
    QLineEdit = None  # type: ignore[assignment]
    QMainWindow = None  # type: ignore[assignment]
    QPushButton = None  # type: ignore[assignment]
    QPlainTextEdit = None  # type: ignore[assignment]
    QVBoxLayout = None  # type: ignore[assignment]
    QWidget = None  # type: ignore[assignment]


@dataclass(frozen=True, slots=True)
class StatusPanelData:
    player_name: str
    location_name: str
    current_time: str
    hunger: int
    health: int
    willpower: int
    humanity: int


@dataclass(frozen=True, slots=True)
class GuiCommandOutcome:
    output_text: str
    should_quit: bool = False


class SessionBackend(Protocol):
    def get_startup_text(self) -> str:
        ...

    def get_world_state(self) -> WorldState:
        ...

    def process_input(self, raw_input: str) -> CommandResult:
        ...


def build_status_panel_data(world_state: WorldState) -> StatusPanelData:
    location_id = world_state.player.location_id
    if location_id is None:
        location_name = "None"
    else:
        location = world_state.locations.get(location_id)
        location_name = location.name if location is not None else location_id

    return StatusPanelData(
        player_name=world_state.player.name,
        location_name=location_name,
        current_time=world_state.current_time,
        hunger=world_state.player.hunger,
        health=world_state.player.health,
        willpower=world_state.player.willpower,
        humanity=world_state.player.humanity,
    )


def format_status_panel_text(world_state: WorldState) -> str:
    data = build_status_panel_data(world_state)
    return "\n".join(
        [
            f"Player: {data.player_name}",
            f"Location: {data.location_name}",
            f"Time: {data.current_time}",
            f"Hunger: {data.hunger}",
            f"Health: {data.health}",
            f"Willpower: {data.willpower}",
            f"Humanity: {data.humanity}",
        ]
    )


class GuiSessionController:
    def __init__(
        self,
        session: SessionBackend | None = None,
        scene_provider: SceneNarrativeProvider | None = None,
        startup_notice: str | None = None,
    ) -> None:
        self._session = session if session is not None else GameSession(scene_provider=scene_provider)
        self._startup_notice = startup_notice

    def startup_text(self) -> str:
        startup_text = self._session.get_startup_text()
        if self._startup_notice:
            return f"{self._startup_notice}\n\n{startup_text}"
        return startup_text

    def status_data(self) -> StatusPanelData:
        return build_status_panel_data(self._session.get_world_state())

    def status_text(self) -> str:
        return format_status_panel_text(self._session.get_world_state())

    def submit_command(self, raw_input: str) -> GuiCommandOutcome:
        try:
            result = self._session.process_input(raw_input)
        except CommandParseError as exc:
            return GuiCommandOutcome(output_text=f"Input error: {exc}")
        except WorldStateError as exc:
            return GuiCommandOutcome(output_text=f"Action failed: {exc}")
        return GuiCommandOutcome(output_text=result.output_text, should_quit=result.should_quit)


if QApplication is not None:
    class GameWindow(QMainWindow):
        def __init__(
            self,
            session: SessionBackend | None = None,
            scene_provider: SceneNarrativeProvider | None = None,
            startup_notice: str | None = None,
        ) -> None:
            super().__init__()
            self._controller = GuiSessionController(
                session=session,
                scene_provider=scene_provider,
                startup_notice=startup_notice,
            )
            self.setWindowTitle("Vampire: The Masquerade Storyteller")
            self.resize(960, 720)

            central_widget = QWidget(self)
            self.setCentralWidget(central_widget)

            root_layout = QVBoxLayout(central_widget)
            root_layout.setSpacing(12)

            self._output_panel = QPlainTextEdit()
            self._output_panel.setReadOnly(True)
            self._output_panel.setPlaceholderText("Scene output will appear here.")
            root_layout.addWidget(self._output_panel, 3)

            status_group = QGroupBox("Status")
            status_layout = QFormLayout(status_group)
            self._status_labels = {
                "player_name": QLabel(),
                "location_name": QLabel(),
                "current_time": QLabel(),
                "hunger": QLabel(),
                "health": QLabel(),
                "willpower": QLabel(),
                "humanity": QLabel(),
            }
            status_layout.addRow("Player", self._status_labels["player_name"])
            status_layout.addRow("Location", self._status_labels["location_name"])
            status_layout.addRow("Time", self._status_labels["current_time"])
            status_layout.addRow("Hunger", self._status_labels["hunger"])
            status_layout.addRow("Health", self._status_labels["health"])
            status_layout.addRow("Willpower", self._status_labels["willpower"])
            status_layout.addRow("Humanity", self._status_labels["humanity"])
            root_layout.addWidget(status_group, 0)

            command_row = QHBoxLayout()
            self._command_input = QLineEdit()
            self._command_input.setPlaceholderText("Enter a command...")
            self._submit_button = QPushButton("Submit")
            command_row.addWidget(self._command_input, 1)
            command_row.addWidget(self._submit_button, 0)
            root_layout.addLayout(command_row)

            self._footer_label = QLabel("Commands: look, move, wait, investigate, save, load, status, help, quit")
            self._footer_label.setFrameShape(QFrame.Shape.StyledPanel)
            self._footer_label.setWordWrap(True)
            root_layout.addWidget(self._footer_label, 0)

            self._submit_button.clicked.connect(self._handle_submit)
            self._command_input.returnPressed.connect(self._handle_submit)

            self._output_panel.setPlainText(self._controller.startup_text())
            self.refresh_status_panel()

        def refresh_status_panel(self) -> None:
            data = self._controller.status_data()
            self._status_labels["player_name"].setText(data.player_name)
            self._status_labels["location_name"].setText(data.location_name)
            self._status_labels["current_time"].setText(data.current_time)
            self._status_labels["hunger"].setText(str(data.hunger))
            self._status_labels["health"].setText(str(data.health))
            self._status_labels["willpower"].setText(str(data.willpower))
            self._status_labels["humanity"].setText(str(data.humanity))

        def _append_command_block(self, raw_input: str, output_text: str) -> None:
            if self._output_panel.toPlainText():
                self._output_panel.appendPlainText("")
            self._output_panel.appendPlainText(f"> {raw_input}")
            self._output_panel.appendPlainText(output_text)

        def _handle_submit(self) -> None:
            raw_input = self._command_input.text().strip()
            if not raw_input:
                return

            self._command_input.clear()
            outcome = self._controller.submit_command(raw_input)
            self._append_command_block(raw_input, outcome.output_text)
            self.refresh_status_panel()
            if outcome.should_quit:
                self.close()


def run_gui() -> None:
    scene_provider, notice = build_scene_provider()
    if QApplication is None:
        raise RuntimeError("PySide6 is required to run the GUI")

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    window = GameWindow(scene_provider=scene_provider, startup_notice=notice)
    window.show()

    app.exec()
