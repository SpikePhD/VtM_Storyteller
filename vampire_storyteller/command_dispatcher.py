from __future__ import annotations

from .actions import wait_action
from .dialogue_engine import resolve_talk_result
from .command_models import (
    Command,
    HelpCommand,
    InvestigateCommand,
    LoadCommand,
    LookCommand,
    MoveCommand,
    QuitCommand,
    SaveCommand,
    StatusCommand,
    TalkCommand,
    WaitCommand,
)
from .command_result import CommandResult
from .map_engine import move_player
from .text_renderers import render_help_text, render_status_text
from .world_state import WorldState


def execute_command(world_state: WorldState, command: Command) -> CommandResult:
    if isinstance(command, LookCommand):
        return CommandResult(output_text="", render_scene=True)

    if isinstance(command, StatusCommand):
        return CommandResult(output_text=render_status_text(world_state))

    if isinstance(command, HelpCommand):
        return CommandResult(output_text=render_help_text())

    if isinstance(command, MoveCommand):
        move_player(world_state, command.destination_id)
        return CommandResult(output_text="", render_scene=True)

    if isinstance(command, WaitCommand):
        wait_action(world_state, command.minutes)
        return CommandResult(output_text="", render_scene=True)

    if isinstance(command, TalkCommand):
        talk_result = resolve_talk_result(world_state, command.npc_id, command.dialogue_metadata)
        return CommandResult(
            output_text=talk_result.output_text,
            conversation_focus_npc_id=talk_result.conversation_focus_npc_id,
        )

    if isinstance(command, InvestigateCommand):
        return CommandResult(output_text="", render_scene=True)

    if isinstance(command, SaveCommand):
        return CommandResult(output_text="")

    if isinstance(command, LoadCommand):
        return CommandResult(output_text="")

    if isinstance(command, QuitCommand):
        return CommandResult(output_text="Goodbye.", should_quit=True)

    raise TypeError(f"unsupported command type: {type(command).__name__}")
