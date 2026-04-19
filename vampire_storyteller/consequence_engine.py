from __future__ import annotations

from .adventure_loader import AdventureContentError, load_adv1_plot_investigation_rules, load_adv1_plot_outcome_definitions
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
        outcome = next(
            (definition for definition in load_adv1_plot_outcome_definitions() if definition.id == plot.id),
            None,
        )
        message = rules.success_message
        if outcome is None:
            raise AdventureContentError(f"Missing ADV1 plot outcome definition for '{plot.id}'.")
        plot.resolution_summary = outcome.resolved_event_text
        plot.learned_outcome = outcome.learned_outcome
        plot.closing_beat = outcome.closing_beat
        _adjust_trust_for_resolution(world_state, outcome.trust_adjustments)
    else:
        message = rules.failure_message
    world_state.append_event(
        EventLogEntry(
            timestamp=world_state.current_time,
            description=message,
            involved_entities=[world_state.player.id, plot.id, player_location_id],
        )
    )
    if roll_result is not None and roll_result.is_success and plot.closing_beat:
        world_state.append_event(
            EventLogEntry(
                timestamp=world_state.current_time,
                description=plot.closing_beat,
                involved_entities=[world_state.player.id, plot.id, player_location_id],
            )
        )
    messages.append(message)
    return messages


def _adjust_trust_for_resolution(world_state: WorldState, trust_adjustments: dict[str, int]) -> None:
    for npc_id, delta in trust_adjustments.items():
        npc = world_state.npcs.get(npc_id)
        if npc is not None:
            npc.trust_level = max(0, npc.trust_level + delta)
