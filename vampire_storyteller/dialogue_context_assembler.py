from __future__ import annotations

from dataclasses import dataclass

from .adventure_loader import (
    AdventureContentError,
    Adv1DialogueDossierDefinition,
    load_adv1_dialogue_dossiers,
    load_adv1_plot_progression_rules,
)
from .command_models import TalkCommand
from .dialogue_adjudication import DialogueAdjudicationOutcome
from .models import NPCDialogueProfile
from .social_models import SocialOutcomePacket
from .world_state import WorldState


@dataclass(frozen=True, slots=True)
class DialogueTurnContext:
    npc_id: str
    npc_name: str
    npc_role: str
    npc_trust_level: int
    npc_profile: NPCDialogueProfile
    npc_dossier: Adv1DialogueDossierDefinition | None
    player_name: str
    location_name: str
    plot_id: str
    plot_name: str
    plot_stage: str
    lead_flag_active: bool
    conversation_stance: str
    conversation_subtopic: str | None
    social_outcome: SocialOutcomePacket | None
    authorized_fact_cards: tuple[object, ...]


def assemble_dialogue_context(
    world_state: WorldState,
    command: TalkCommand,
    dialogue_adjudication: DialogueAdjudicationOutcome,
    social_outcome: SocialOutcomePacket | None,
    authorized_fact_cards: tuple[object, ...],
) -> DialogueTurnContext:
    npc = world_state.npcs.get(command.npc_id)
    if npc is None:
        raise RuntimeError(f"npc '{command.npc_id}' is missing")

    plot_rules = load_adv1_plot_progression_rules()
    plot = world_state.plots.get(plot_rules.plot_id)
    location = world_state.locations.get(world_state.player.location_id or "")
    location_name = location.name if location is not None else (world_state.player.location_id or "unknown location")
    dossier = _load_dialogue_dossier(command.npc_id)

    return DialogueTurnContext(
        npc_id=npc.id,
        npc_name=npc.name,
        npc_role=npc.role,
        npc_trust_level=npc.trust_level,
        npc_profile=npc.dialogue_profile,
        npc_dossier=dossier,
        player_name=world_state.player.name,
        location_name=location_name,
        plot_id=plot_rules.plot_id,
        plot_name=plot_rules.plot_name,
        plot_stage=plot.stage if plot is not None else "",
        lead_flag_active=plot_rules.talk_required_story_flag in set(world_state.story_flags),
        conversation_stance=dialogue_adjudication.conversation_stance.value,
        conversation_subtopic=command.conversation_subtopic.value if command.conversation_subtopic is not None else None,
        social_outcome=social_outcome,
        authorized_fact_cards=authorized_fact_cards,
    )


def _load_dialogue_dossier(npc_id: str) -> Adv1DialogueDossierDefinition | None:
    try:
        dossier_state = load_adv1_dialogue_dossiers()
    except AdventureContentError:
        return None
    return dossier_state.npc_definitions.get(npc_id)
