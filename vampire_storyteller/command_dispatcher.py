from __future__ import annotations

from .actions import wait_action
from .adventure_loader import load_adv1_dialogue_hook_definitions
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
        return CommandResult(output_text=_talk_to_npc(world_state, command.npc_id))

    if isinstance(command, InvestigateCommand):
        return CommandResult(output_text="", render_scene=True)

    if isinstance(command, SaveCommand):
        return CommandResult(output_text="")

    if isinstance(command, LoadCommand):
        return CommandResult(output_text="")

    if isinstance(command, QuitCommand):
        return CommandResult(output_text="Goodbye.", should_quit=True)

    raise TypeError(f"unsupported command type: {type(command).__name__}")


def _talk_to_npc(world_state: WorldState, npc_id: str) -> str:
    npc = world_state.npcs.get(npc_id)
    if npc is None:
        return f"Talk is blocked: no NPC with id '{npc_id}' exists."

    if npc.location_id != world_state.player.location_id:
        location = world_state.locations.get(world_state.player.location_id or "")
        location_name = location.name if location is not None else (world_state.player.location_id or "unknown location")
        return f"Talk is blocked: {npc.name} is not present at {location_name}."

    plot = world_state.plots.get("plot_1")
    current_stage = plot.stage if plot is not None else ""
    hooks = load_adv1_dialogue_hook_definitions()
    hook = _find_dialogue_hook(hooks, npc_id, current_stage, npc.trust_level)
    if hook is not None:
        _adjust_npc_trust(world_state, npc_id, hook.trust_delta)
        return hook.dialogue_text

    fallback = _find_dialogue_fallback(hooks, npc_id)
    if fallback is not None:
        return f"Talk is blocked: {fallback}"

    return f"{npc.name} has nothing useful to say right now."


def _find_dialogue_hook(hooks, npc_id: str, plot_stage: str, current_trust_level: int):
    matching_hook = None
    for hook in hooks:
        if hook.npc_id != npc_id or hook.required_plot_id != "plot_1" or hook.required_plot_stage != plot_stage:
            continue
        if hook.minimum_trust_level > current_trust_level:
            continue
        if matching_hook is None or hook.minimum_trust_level > matching_hook.minimum_trust_level:
            matching_hook = hook
    return matching_hook


def _adjust_npc_trust(world_state: WorldState, npc_id: str, delta: int) -> None:
    if delta == 0:
        return
    npc = world_state.npcs.get(npc_id)
    if npc is None:
        return
    npc.trust_level = max(0, npc.trust_level + delta)


def _find_dialogue_fallback(hooks, npc_id: str) -> str | None:
    for hook in hooks:
        if hook.npc_id == npc_id:
            return hook.blocked_text
    return None
