from __future__ import annotations

from .command_models import Command, InvestigateCommand, MoveCommand, TalkCommand, WaitCommand
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

    if isinstance(command, InvestigateCommand):
        if (
            plot.stage == rules.wait_from_stage
            and world_state.player.location_id == rules.wait_location_id
        ):
            previous_stage = plot.stage
            plot.stage = rules.wait_to_stage
            world_state.add_story_flag("church_records_reviewed")
            messages.append(f"Plot '{plot.name}' advanced from {previous_stage} to {plot.stage}.")
            world_state.append_event(
                EventLogEntry(
                    timestamp=world_state.current_time,
                    description=messages[-1],
                    involved_entities=[world_state.player.id, plot.id, rules.wait_location_id],
                )
            )
        return messages

    if isinstance(command, TalkCommand):
        if _eliza_church_records_lead_applies(world_state, command, rules):
            previous_stage = plot.stage
            plot.stage = rules.talk_to_stage
            world_state.add_story_flag("eliza_shared_church_records_lead")
            messages.append(f"Plot '{plot.name}' advanced from {previous_stage} to {plot.stage}.")
            world_state.append_event(
                EventLogEntry(
                    timestamp=world_state.current_time,
                    description=messages[-1],
                    involved_entities=[world_state.player.id, plot.id, command.npc_id],
                )
            )
            return messages

        if (
            plot.stage == rules.talk_from_stage
            and command.npc_id == rules.talk_npc_id
            and world_state.player.location_id == rules.talk_location_id
        ):
            npc = world_state.npcs.get(command.npc_id)
            if (
                npc is not None
                and npc.trust_level >= rules.talk_minimum_trust_level
                and rules.talk_required_story_flag in world_state.story_flags
            ):
                previous_stage = plot.stage
                plot.stage = rules.talk_to_stage
                messages.append(f"Plot '{plot.name}' advanced from {previous_stage} to {plot.stage}.")
                world_state.append_event(
                    EventLogEntry(
                        timestamp=world_state.current_time,
                        description=messages[-1],
                        involved_entities=[world_state.player.id, plot.id, command.npc_id],
                    )
                )

    return messages


def _eliza_church_records_lead_applies(world_state: WorldState, command: TalkCommand, rules) -> bool:
    if command.npc_id != "npc_2":
        return False
    if world_state.player.location_id != "loc_church":
        return False
    plot = world_state.plots.get(rules.plot_id)
    if plot is None or plot.stage != "church_visited":
        return False
    metadata = command.dialogue_metadata
    if metadata is None:
        return False
    normalized_text = _normalize_dialogue_text(
        " ".join(
            part
            for part in (
                metadata.topic or "",
                metadata.speech_text,
                metadata.utterance_text,
            )
            if part
        )
    )
    return any(
        phrase in normalized_text
        for phrase in (
            "church records",
            "record shelves",
            "records",
            "ledger",
        )
    )


def _normalize_dialogue_text(raw_text: str) -> str:
    return " ".join(raw_text.lower().replace("-", " ").split())
