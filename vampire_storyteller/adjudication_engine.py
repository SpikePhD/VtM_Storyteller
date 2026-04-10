from __future__ import annotations

from dataclasses import dataclass

from .adventure_loader import PlotInvestigationRules, load_adv1_plot_investigation_rules
from .command_models import Command, InvestigateCommand
from .world_state import WorldState


@dataclass(frozen=True, slots=True)
class AdjudicationDecision:
    requires_roll: bool
    roll_pool: int | None
    difficulty: int | None
    reason: str
    blocked_feedback: str | None = None


def adjudicate_command(world_state: WorldState, command: Command) -> AdjudicationDecision:
    rules = load_adv1_plot_investigation_rules()
    if isinstance(command, InvestigateCommand):
        if _investigation_requires_roll(world_state, rules):
            return AdjudicationDecision(
                requires_roll=rules.requires_roll,
                roll_pool=rules.roll_pool,
                difficulty=rules.difficulty,
                reason=(
                    f"investigate at {rules.location_id} with {rules.required_stage} requires a roll"
                ),
            )
        return AdjudicationDecision(
            requires_roll=False,
            roll_pool=None,
            difficulty=None,
            reason="investigate does not require a roll in the current state",
            blocked_feedback=_investigation_blocked_feedback(world_state, rules),
        )

    return AdjudicationDecision(
        requires_roll=False,
        roll_pool=None,
        difficulty=None,
        reason="no roll required",
    )


def _investigation_requires_roll(world_state: WorldState, rules: PlotInvestigationRules) -> bool:
    if world_state.player.location_id != rules.location_id:
        return False

    plot = world_state.plots.get(rules.plot_id)
    return plot is not None and plot.active and plot.stage == rules.required_stage


def _investigation_blocked_feedback(world_state: WorldState, rules: PlotInvestigationRules) -> str:
    plot = world_state.plots.get(rules.plot_id)
    location = world_state.locations.get(rules.location_id)
    location_name = location.name if location is not None else rules.location_id

    if plot is None or not plot.active:
        return f"Investigate is blocked: {rules.plot_name} is no longer active."

    if world_state.player.location_id != rules.location_id:
        if plot.stage == rules.required_stage:
            return f"Investigate is blocked: {rules.plot_name} can only be resolved at {location_name}."
        return (
            f"Investigate is blocked: {rules.plot_name} must reach {rules.required_stage} "
            f"before it can be resolved at {location_name}."
        )

    if plot.stage != rules.required_stage:
        return (
            f"Investigate is blocked: {rules.plot_name} is currently at {plot.stage} "
            f"and needs {rules.required_stage} first."
        )

    return f"Investigate is blocked: {rules.plot_name} cannot be resolved right now."
