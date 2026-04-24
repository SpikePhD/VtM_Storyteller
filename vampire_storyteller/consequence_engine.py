from __future__ import annotations

from .action_resolution import (
    ActionAdjudicationOutcome,
    ActionCheckOutcome,
    ActionConsequenceSummary,
    ActionResolutionKind,
)
from .adventure_loader import AdventureContentError, load_adv1_plot_investigation_rules, load_adv1_plot_outcome_definitions
from .command_models import Command, InvestigateCommand
from .dice_engine import DeterministicCheckKind, DiceRollResult
from .models import EventLogEntry
from .world_state import WorldState


def apply_post_resolution_consequences(
    world_state: WorldState,
    command: Command,
    adjudication: ActionAdjudicationOutcome,
    check: ActionCheckOutcome | None = None,
) -> ActionConsequenceSummary:
    rules = load_adv1_plot_investigation_rules()
    messages: list[str] = []
    applied_effects: list[str] = []

    if not isinstance(command, InvestigateCommand):
        return ActionConsequenceSummary()

    if adjudication.resolution_kind is not ActionResolutionKind.ROLL_GATED or check is None:
        return ActionConsequenceSummary()

    if check.kind is not DeterministicCheckKind.INVESTIGATION:
        return ActionConsequenceSummary()

    player_location_id = world_state.player.location_id
    if player_location_id != rules.location_id:
        return ActionConsequenceSummary()

    plot = world_state.plots.get(rules.plot_id)
    if plot is None or not plot.active or plot.stage != rules.required_stage:
        return ActionConsequenceSummary()

    if world_state.locations.get(player_location_id) is None:
        return ActionConsequenceSummary()

    if check.is_success:
        plot.stage = rules.success_stage
        plot.active = rules.success_active
        outcome = next((definition for definition in load_adv1_plot_outcome_definitions() if definition.id == plot.id), None)
        message = rules.success_message
        if outcome is None:
            raise AdventureContentError(f"Missing ADV1 plot outcome definition for '{plot.id}'.")
        plot.resolution_summary = outcome.resolved_event_text
        plot.learned_outcome = outcome.learned_outcome
        plot.closing_beat = outcome.closing_beat
        _adjust_trust_for_resolution(world_state, outcome.trust_adjustments)
        applied_effects.extend(
            [
                "investigate_resolution_success",
                "plot_resolution_updated",
                "trust_adjustments_applied",
            ]
        )
    else:
        message = rules.failure_message
        world_state.add_story_flag("dock_partial_trace_found")
        applied_effects.extend(
            [
                "investigate_resolution_failure",
                "dock_partial_trace_recorded",
            ]
        )

    world_state.append_event(
        EventLogEntry(
            timestamp=world_state.current_time,
            description=message,
            involved_entities=[world_state.player.id, plot.id, player_location_id],
        )
    )
    messages.append(message)

    if check.is_success and plot.closing_beat:
        world_state.append_event(
            EventLogEntry(
                timestamp=world_state.current_time,
                description=plot.closing_beat,
                involved_entities=[world_state.player.id, plot.id, player_location_id],
            )
        )
        applied_effects.append("closing_beat_logged")

    return ActionConsequenceSummary(messages=tuple(messages), applied_effects=tuple(applied_effects))


def apply_consequences(
    world_state: WorldState,
    command: Command,
    roll_result: DiceRollResult | None = None,
) -> list[str]:
    if roll_result is None:
        return []

    check = ActionCheckOutcome(
        kind=DeterministicCheckKind.INVESTIGATION,
        seed="compatibility-wrapper",
        roll_pool=roll_result.pool,
        difficulty=roll_result.difficulty,
        individual_rolls=list(roll_result.individual_rolls),
        successes=roll_result.successes,
        is_success=roll_result.is_success,
    )
    adjudication = ActionAdjudicationOutcome(
        resolution_kind=ActionResolutionKind.ROLL_GATED,
        reason="compatibility wrapper for legacy consequence tests",
        roll_pool=roll_result.pool,
        difficulty=roll_result.difficulty,
    )
    return list(apply_post_resolution_consequences(world_state, command, adjudication, check).messages)


def _adjust_trust_for_resolution(world_state: WorldState, trust_adjustments: dict[str, int]) -> None:
    for npc_id, delta in trust_adjustments.items():
        npc = world_state.npcs.get(npc_id)
        if npc is not None:
            npc.social_state.trust = max(0, npc.social_state.trust + delta)
            npc.trust_level = npc.social_state.trust
