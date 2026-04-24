from __future__ import annotations

from .action_resolution import AdjudicationDecision, ActionBlockReason, ActionResolutionKind
from .adventure_loader import PlotInvestigationRules, load_adv1_plot_investigation_rules, load_adv1_plot_progression_rules
from .command_models import Command, HelpCommand, InvestigateCommand, LoadCommand, LookCommand, MoveCommand, QuitCommand, SaveCommand, StatusCommand, TalkCommand, WaitCommand
from .dice_engine import DeterministicCheckKind, DeterministicCheckSpecification
from .world_state import WorldState


def adjudicate_command(world_state: WorldState, command: Command) -> AdjudicationDecision:
    if isinstance(command, (LookCommand, StatusCommand, HelpCommand, WaitCommand, SaveCommand, LoadCommand, QuitCommand)):
        return _automatic_decision(f"{type(command).__name__.removesuffix('Command').lower()} resolves automatically")

    if isinstance(command, MoveCommand):
        return _adjudicate_move(world_state, command)

    if isinstance(command, TalkCommand):
        return _adjudicate_talk(world_state, command)

    if isinstance(command, InvestigateCommand):
        return _adjudicate_investigate(world_state, command)

    return _automatic_decision("no roll required")


def _automatic_decision(reason: str) -> AdjudicationDecision:
    return AdjudicationDecision(
        resolution_kind=ActionResolutionKind.AUTOMATIC,
        reason=reason,
    )


def _blocked_decision(reason: str, blocked_feedback: str, block_reason: ActionBlockReason) -> AdjudicationDecision:
    return AdjudicationDecision(
        resolution_kind=ActionResolutionKind.BLOCKED,
        reason=reason,
        blocked_feedback=blocked_feedback,
        block_reason=block_reason,
    )


def _check_gated_decision_with_spec(reason: str, check_spec: DeterministicCheckSpecification) -> AdjudicationDecision:
    return AdjudicationDecision(
        resolution_kind=ActionResolutionKind.ROLL_GATED,
        reason=reason,
        check_spec=check_spec,
        roll_pool=check_spec.roll_pool,
        difficulty=check_spec.difficulty,
    )


def _adjudicate_move(world_state: WorldState, command: MoveCommand) -> AdjudicationDecision:
    source_location_id = world_state.player.location_id
    if source_location_id is None:
        return _blocked_decision(
            reason="move requires a current player location",
            blocked_feedback="Move is blocked: player has no current location.",
            block_reason=ActionBlockReason.UNSUPPORTED_CONTEXT,
        )

    source_location = world_state.locations.get(source_location_id)
    if source_location is None:
        return _blocked_decision(
            reason=f"move source location '{source_location_id}' is missing",
            blocked_feedback=f"Move is blocked: source location '{source_location_id}' does not exist.",
            block_reason=ActionBlockReason.UNSUPPORTED_CONTEXT,
        )

    destination = world_state.locations.get(command.destination_id)
    if destination is None:
        return _blocked_decision(
            reason=f"move destination '{command.destination_id}' is invalid",
            blocked_feedback=f"Move is blocked: destination '{command.destination_id}' does not exist.",
            block_reason=ActionBlockReason.INVALID_DESTINATION,
        )

    if command.destination_id not in source_location.connected_locations:
        return _blocked_decision(
            reason=f"move destination '{command.destination_id}' is not connected to '{source_location_id}'",
            blocked_feedback=(
                f"Move is blocked: destination '{command.destination_id}' is not connected to source '{source_location_id}'."
            ),
            block_reason=ActionBlockReason.PREREQUISITE_NOT_MET,
        )

    if source_location.travel_time.get(command.destination_id) is None:
        return _blocked_decision(
            reason=f"move travel time from '{source_location_id}' to '{command.destination_id}' is missing",
            blocked_feedback=(
                f"Move is blocked: travel time from '{source_location_id}' to '{command.destination_id}' is not defined."
            ),
            block_reason=ActionBlockReason.PREREQUISITE_NOT_MET,
        )

    return _automatic_decision("move destination is valid")


def _adjudicate_talk(world_state: WorldState, command: TalkCommand) -> AdjudicationDecision:
    npc = world_state.npcs.get(command.npc_id)
    if npc is None:
        return _blocked_decision(
            reason=f"talk target '{command.npc_id}' does not exist",
            blocked_feedback=f"Talk is blocked: no NPC with id '{command.npc_id}' exists.",
            block_reason=ActionBlockReason.TARGET_NOT_PRESENT,
        )

    player_location_id = world_state.player.location_id
    if player_location_id is None:
        return _blocked_decision(
            reason="talk requires a current player location",
            blocked_feedback="Talk is blocked: player has no current location.",
            block_reason=ActionBlockReason.UNSUPPORTED_CONTEXT,
        )

    if npc.location_id != player_location_id:
        location = world_state.locations.get(player_location_id)
        location_name = location.name if location is not None else player_location_id
        return _blocked_decision(
            reason=f"talk target '{command.npc_id}' is not present at '{player_location_id}'",
            blocked_feedback=f"Talk is blocked: {npc.name} is not present at {location_name}.",
            block_reason=ActionBlockReason.TARGET_NOT_PRESENT,
        )

    return _automatic_decision("talk target is present")


def _adjudicate_investigate(world_state: WorldState, command: InvestigateCommand) -> AdjudicationDecision:
    rules = load_adv1_plot_investigation_rules()
    plot = world_state.plots.get(rules.plot_id)
    if plot is None or not plot.active:
        return _blocked_decision(
            reason=f"investigate target plot '{rules.plot_id}' is inactive",
            blocked_feedback=_investigation_blocked_feedback(world_state, rules),
            block_reason=ActionBlockReason.TARGET_INACTIVE,
        )

    progression_rules = load_adv1_plot_progression_rules()
    if (
        world_state.player.location_id == progression_rules.wait_location_id
        and plot.stage == progression_rules.wait_from_stage
    ):
        return _automatic_decision("church records investigation can confirm the dock lead")

    if not _investigation_requires_roll(world_state, rules):
        return _blocked_decision(
            reason="investigate prerequisites are not met",
            blocked_feedback=_investigation_blocked_feedback(world_state, rules),
            block_reason=ActionBlockReason.PREREQUISITE_NOT_MET,
        )

    if rules.requires_roll:
        return _check_gated_decision_with_spec(
            reason=f"investigate at {rules.location_id} with {rules.required_stage} requires a roll",
            check_spec=_investigation_check_spec(world_state, rules),
        )

    return _automatic_decision("investigate does not require a roll in the current state")


def _investigation_check_spec(world_state: WorldState, rules: PlotInvestigationRules) -> DeterministicCheckSpecification:
    return DeterministicCheckSpecification(
        kind=DeterministicCheckKind.INVESTIGATION,
        seed_parts=(
            world_state.current_time,
            "investigate",
            world_state.player.id,
        ),
        roll_pool=rules.roll_pool,
        difficulty=rules.difficulty,
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
