from __future__ import annotations

from .adventure_loader import load_adv1_plot_investigation_rules
from .command_models import Command, InvestigateCommand
from .dice_engine import DiceRollResult
from .models import EventLogEntry
from .world_state import WorldState


def apply_consequences(
    world_state: WorldState,
    command: Command,
    roll_result: DiceRollResult | None = None,
) -> list[str]:
    rules = load_adv1_plot_investigation_rules()
    messages: list[str] = []
    if not isinstance(command, InvestigateCommand):
        return messages

    player_location_id = world_state.player.location_id
    if player_location_id != rules.location_id:
        return messages

    plot = world_state.plots.get(rules.plot_id)
    if plot is None or not plot.active or plot.stage != rules.required_stage:
        return messages

    location = world_state.locations.get(player_location_id)
    if location is None:
        return messages

    if roll_result is None:
        return messages

    if roll_result.is_success:
        plot.stage = rules.success_stage
        plot.active = rules.success_active
        message = rules.success_message
    else:
        message = rules.failure_message
    world_state.append_event(
        EventLogEntry(
            timestamp=world_state.current_time,
            description=message,
            involved_entities=[world_state.player.id, plot.id, player_location_id],
        )
    )
    messages.append(message)
    return messages
