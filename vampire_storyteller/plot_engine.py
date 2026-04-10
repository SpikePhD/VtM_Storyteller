from __future__ import annotations

from .command_models import Command, MoveCommand, WaitCommand
from .adventure_loader import load_adv1_plot_progression_rules
from .models import EventLogEntry
from .world_state import WorldState


def advance_plots(world_state: WorldState, command: Command) -> list[str]:
    rules = load_adv1_plot_progression_rules()
    messages: list[str] = []
    plot = world_state.plots.get(rules.plot_id)
    if plot is None or not plot.active:
        return messages

    if isinstance(command, MoveCommand):
        if plot.stage == rules.move_from_stage and command.destination_id == rules.move_destination_id:
            previous_stage = plot.stage
            plot.stage = rules.move_to_stage
            messages.append(f"Plot '{plot.name}' advanced from {previous_stage} to {plot.stage}.")
            world_state.append_event(
                EventLogEntry(
                    timestamp=world_state.current_time,
                    description=messages[-1],
                    involved_entities=[world_state.player.id, plot.id, command.destination_id],
                )
            )
        return messages

    if isinstance(command, WaitCommand):
        if (
            plot.stage == rules.wait_from_stage
            and command.minutes >= rules.wait_minimum_minutes
            and world_state.player.location_id == rules.wait_location_id
        ):
            previous_stage = plot.stage
            plot.stage = rules.wait_to_stage
            messages.append(f"Plot '{plot.name}' advanced from {previous_stage} to {plot.stage}.")
            world_state.append_event(
                EventLogEntry(
                    timestamp=world_state.current_time,
                    description=messages[-1],
                    involved_entities=[world_state.player.id, plot.id, rules.wait_location_id],
                )
            )

    return messages
