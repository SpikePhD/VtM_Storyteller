from __future__ import annotations

from pathlib import Path

from .adjudication_engine import adjudicate_command
from .command_dispatcher import execute_command
from .command_models import Command, InvestigateCommand, LoadCommand, MoveCommand, SaveCommand, TalkCommand, WaitCommand
from .command_parser import parse_command
from .command_result import CommandResult
from .consequence_engine import apply_consequences
from .dice_engine import roll_dice
from .data_paths import ensure_adventure_directories, get_default_save_path
from .input_interpreter import InputInterpreter
from .models import EventLogEntry
from .npc_engine import update_npcs_for_current_time
from .narrative_provider import DeterministicSceneNarrativeProvider, SceneNarrativeProvider
from .plot_engine import advance_plots
from .sample_world import build_sample_world
from .serialization import load_world_state, save_world_state
from .world_state import WorldState


class GameSession:
    def __init__(
        self,
        world_state: WorldState | None = None,
        scene_provider: SceneNarrativeProvider | None = None,
        save_path: str | Path | None = None,
    ) -> None:
        self._world_state = world_state if world_state is not None else build_sample_world()
        self._scene_provider = scene_provider if scene_provider is not None else DeterministicSceneNarrativeProvider()
        self._fallback_scene_provider = DeterministicSceneNarrativeProvider()
        self._input_interpreter = InputInterpreter()
        self._save_path = Path(save_path) if save_path is not None else get_default_save_path()

    def get_startup_text(self) -> str:
        return self._render_scene_text()

    def process_input(self, raw_input: str) -> CommandResult:
        interpretation = self._input_interpreter.interpret(raw_input, self._world_state)
        command_input = interpretation.canonical_command if not interpretation.fallback_to_parser else raw_input
        command = parse_command(command_input)
        if isinstance(command, SaveCommand):
            ensure_adventure_directories()
            save_world_state(self._world_state, self._save_path)
            return CommandResult(output_text=f"Game saved to {self._save_path.as_posix()}.")

        if isinstance(command, LoadCommand):
            if not self._save_path.exists():
                return CommandResult(output_text=f"No save file found at {self._save_path.as_posix()}.")
            self._world_state = load_world_state(self._save_path)
            return CommandResult(output_text=self._render_scene_text(), render_scene=True)

        adjudication = adjudicate_command(self._world_state, command)
        if isinstance(command, InvestigateCommand) and not adjudication.requires_roll:
            return CommandResult(
                output_text=adjudication.blocked_feedback or "Investigate is blocked.",
            )
        result = execute_command(self._world_state, command)
        if result.should_quit:
            return result

        if isinstance(command, TalkCommand):
            plot_messages = advance_plots(self._world_state, command)
            if plot_messages:
                result = CommandResult(
                    output_text="\n".join([result.output_text, *plot_messages]) if result.output_text else "\n".join(plot_messages),
                    should_quit=result.should_quit,
                    render_scene=result.render_scene,
                )

        if result.render_scene:
            if isinstance(command, (MoveCommand, WaitCommand)):
                update_npcs_for_current_time(self._world_state)

            advance_plots(self._world_state, command)

            roll_result = None
            if adjudication.requires_roll:
                seed = self._derive_roll_seed(command)
                assert adjudication.roll_pool is not None
                assert adjudication.difficulty is not None
                roll_result = roll_dice(adjudication.roll_pool, adjudication.difficulty, seed=seed)
                self._world_state.append_event(
                    EventLogEntry(
                        timestamp=self._world_state.current_time,
                        description=(
                            f"Rolled {roll_result.pool} dice vs difficulty {roll_result.difficulty}: "
                            f"{roll_result.individual_rolls} -> {roll_result.successes} successes."
                        ),
                        involved_entities=[
                            self._world_state.player.id,
                            "plot_1",
                            self._world_state.player.location_id or "",
                        ],
                    )
                )

            apply_consequences(self._world_state, command, roll_result=roll_result)

            if isinstance(command, InvestigateCommand):
                epilogue_text = self._build_resolution_epilogue()
                if epilogue_text:
                    rendered_scene_text = self._render_scene_text()
                    result = CommandResult(
                        output_text=f"{epilogue_text}\n\n{rendered_scene_text}",
                        should_quit=result.should_quit,
                        render_scene=True,
                    )
                    return result

            result = CommandResult(
                output_text=self._render_scene_text(),
                should_quit=result.should_quit,
                render_scene=True,
            )
        return result

    def get_world_state(self) -> WorldState:
        return self._world_state

    def _render_scene_text(self) -> str:
        try:
            return self._scene_provider.render_scene(self._world_state)
        except Exception:
            self._scene_provider = self._fallback_scene_provider
            return self._fallback_scene_provider.render_scene(self._world_state)

    def _derive_roll_seed(self, command: Command) -> str:
        command_name = command.__class__.__name__.removesuffix("Command").lower()
        player_id = self._world_state.player.id
        return f"{self._world_state.current_time}|{command_name}|{player_id}"

    def _build_resolution_epilogue(self) -> str:
        plot = self._world_state.plots.get("plot_1")
        if plot is None or plot.active:
            return ""
        if not plot.resolution_summary or not plot.learned_outcome or not plot.closing_beat:
            return ""
        return "\n".join(
            [
                plot.resolution_summary,
                f"Learned: {plot.learned_outcome}",
                f"Closing beat: {plot.closing_beat}",
            ]
        )
