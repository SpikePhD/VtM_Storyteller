from __future__ import annotations

from .action_resolution import ActionConsequenceSummary
from .adventure_loader import load_adv1_dialogue_fact_definitions, load_adv1_plot_progression_rules
from .command_models import TalkCommand
from .dialogue_adjudication import DialogueAdjudicationOutcome
from .dialogue_fact_cards import DialogueFactCard
from .models import EventLogEntry
from .social_models import SocialOutcomePacket
from .world_state import WorldState


def select_authorized_fact_cards(
    world_state: WorldState,
    command: TalkCommand,
    dialogue_adjudication: DialogueAdjudicationOutcome,
    social_outcome: SocialOutcomePacket | None,
) -> tuple[DialogueFactCard, ...]:
    fact_state = load_adv1_dialogue_fact_definitions()
    plot_rules = load_adv1_plot_progression_rules()
    plot = world_state.plots.get(plot_rules.plot_id)
    plot_stage = plot.stage if plot is not None else ""
    story_flags = set(world_state.story_flags)
    normalized_text = _normalize_text(command.dialogue_metadata)
    selected: list[DialogueFactCard] = []

    for fact in fact_state.fact_definitions:
        if fact.npc_id != command.npc_id:
            continue
        if fact.plot_id is not None and fact.plot_id != plot_rules.plot_id:
            continue
        if fact.subtopic is not None:
            active_subtopic = command.conversation_subtopic.value if command.conversation_subtopic is not None else None
            if not _subtopic_requirement_matches(fact.subtopic, active_subtopic, dialogue_adjudication.dialogue_domain.value, normalized_text):
                continue
        if fact.required_plot_stages and plot_stage not in fact.required_plot_stages:
            continue
        if fact.required_story_flags and not set(fact.required_story_flags).issubset(story_flags):
            continue
        if fact.allowed_outcome_kinds:
            if social_outcome is None or social_outcome.outcome_kind.value not in fact.allowed_outcome_kinds:
                continue
        if fact.allowed_topic_results:
            if social_outcome is None or social_outcome.topic_result.value not in fact.allowed_topic_results:
                continue
        if fact.requires_check_success is not None:
            if social_outcome is None or social_outcome.check_result is None:
                continue
            if social_outcome.check_result.is_success is not fact.requires_check_success:
                continue
        if fact.required_dialogue_domains and dialogue_adjudication.dialogue_domain.value not in fact.required_dialogue_domains:
            continue
        if fact.required_dialogue_acts:
            dialogue_act = command.dialogue_metadata.dialogue_act.value if command.dialogue_metadata is not None else "unknown"
            if dialogue_act not in fact.required_dialogue_acts:
                continue
        if fact.required_keywords and not any(keyword in normalized_text for keyword in fact.required_keywords):
            continue
        selected.append(
            DialogueFactCard(
                fact_id=fact.fact_id,
                kind=fact.kind,
                summary=fact.summary,
                npc_id=fact.npc_id,
                plot_id=fact.plot_id,
                reveal_plot_stage=fact.reveal_plot_stage,
                reveal_story_flags=fact.reveal_story_flags,
                reveal_trust_level=fact.reveal_trust_level,
            )
        )

    return tuple(selected)


def apply_authorized_fact_progression(
    world_state: WorldState,
    authorized_fact_cards: tuple[DialogueFactCard, ...],
    social_outcome: SocialOutcomePacket | None,
) -> ActionConsequenceSummary:
    if social_outcome is None:
        return ActionConsequenceSummary()

    messages: list[str] = []
    applied_effects: list[str] = []

    for fact_card in authorized_fact_cards:
        if fact_card.plot_id is None:
            continue
        plot = world_state.plots.get(fact_card.plot_id)
        if plot is None or not plot.active:
            continue
        progressed = False
        if fact_card.reveal_plot_stage and plot.stage != fact_card.reveal_plot_stage:
            previous_stage = plot.stage
            plot.stage = fact_card.reveal_plot_stage
            messages.append(f"Dialogue revealed '{fact_card.fact_id}' and advanced {plot.name} from {previous_stage} to {plot.stage}.")
            applied_effects.append(f"{fact_card.fact_id}_plot_stage_revealed")
            world_state.append_event(
                EventLogEntry(
                    timestamp=world_state.current_time,
                    description=messages[-1],
                    involved_entities=[world_state.player.id, plot.id, fact_card.fact_id],
                )
            )
            progressed = True

        for story_flag in fact_card.reveal_story_flags:
            if story_flag in world_state.story_flags:
                continue
            world_state.add_story_flag(story_flag)
            applied_effects.append(f"{fact_card.fact_id}:{story_flag}_added")
            progressed = True

        if fact_card.reveal_trust_level is not None and fact_card.npc_id is not None:
            npc = world_state.npcs.get(fact_card.npc_id)
            if npc is not None and npc.social_state.trust < fact_card.reveal_trust_level:
                npc.social_state.trust = fact_card.reveal_trust_level
                npc.social_state.willingness_to_cooperate = max(npc.social_state.willingness_to_cooperate, 1)
                npc.trust_level = npc.social_state.trust
                applied_effects.append(f"{fact_card.fact_id}:trust_set_to_{fact_card.reveal_trust_level}")
                progressed = True

        if progressed and fact_card.reveal_plot_stage is None and fact_card.reveal_story_flags:
            world_state.append_event(
                EventLogEntry(
                    timestamp=world_state.current_time,
                    description=f"Dialogue revealed '{fact_card.fact_id}' and recorded the relevant lead flag.",
                    involved_entities=[world_state.player.id, plot.id, fact_card.fact_id],
                )
            )

    return ActionConsequenceSummary(messages=tuple(messages), applied_effects=tuple(applied_effects))


def _subtopic_requirement_matches(
    required_subtopic: str,
    active_subtopic: str | None,
    dialogue_domain: str,
    normalized_text: str,
) -> bool:
    if required_subtopic == active_subtopic:
        return True
    if required_subtopic == "missing_ledger" and dialogue_domain in {"lead_topic", "lead_pressure"}:
        if not normalized_text:
            return False
        return any(keyword in normalized_text for keyword in ("dock", "docks", "ledger", "paper trail", "waterline"))
    return False


def _normalize_text(metadata) -> str:
    if metadata is None:
        return ""
    return " ".join(
        piece.lower().replace("-", " ")
        for piece in (metadata.utterance_text, metadata.speech_text, metadata.topic or "")
        if piece
    )
