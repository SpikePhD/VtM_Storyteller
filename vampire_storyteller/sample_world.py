from __future__ import annotations

from .adventure_loader import (
    load_adv1_location_definitions,
    load_adv1_npc_definitions,
    load_adv1_plot_thread_definitions,
    load_adv1_player_seed_data,
    load_adv1_world_state_seed_data,
)
from .models import Location, NPC, PlotThread
from .world_state import WorldState


def build_sample_world() -> WorldState:
    player_seed = load_adv1_player_seed_data()
    seed_data = load_adv1_world_state_seed_data()
    location_definitions = load_adv1_location_definitions()
    npc_definitions = load_adv1_npc_definitions()
    plot_definitions = load_adv1_plot_thread_definitions()

    return WorldState(
        player=player_seed.player,
        npcs={
            npc_definition.id: NPC(
                id=npc_definition.id,
                name=npc_definition.name,
                role=npc_definition.role,
                location_id=npc_definition.starting_location_id,
                attitude_to_player=npc_definition.attitude_to_player,
                goals=[],
                schedule=dict(npc_definition.schedule),
                traits=dict(npc_definition.traits),
            )
            for npc_definition in npc_definitions
        },
        locations={
            location_definition.id: Location(
                id=location_definition.id,
                name=location_definition.name,
                type=location_definition.type,
                connected_locations=list(location_definition.connected_locations),
                travel_time=dict(location_definition.travel_time),
                danger_level=location_definition.danger_level,
            )
            for location_definition in location_definitions
        },
        plots={
            plot_definition.id: PlotThread(
                id=plot_definition.id,
                name=plot_definition.name,
                stage=plot_definition.stage,
                active=plot_definition.active,
                triggers=list(plot_definition.triggers),
                consequences=list(plot_definition.consequences),
            )
            for plot_definition in plot_definitions
        },
        current_time=seed_data.current_time,
    )
