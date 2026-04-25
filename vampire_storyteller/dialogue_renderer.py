from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .action_resolution import ActionCheckOutcome, ActionConsequenceSummary
from .command_models import TalkCommand
from .conversation_context import DialogueHistoryEntry, DialogueMemoryContext
from .dialogue_fact_authorization import select_authorized_fact_cards
from .dialogue_fact_cards import DialogueFactCard
from .dialogue_adjudication import DialogueAdjudicationOutcome
from .dialogue_context_assembler import assemble_dialogue_context
from .adventure_loader import Adv1DialogueDossierDefinition
from .models import NPCDialogueProfile
from .social_models import LogisticsCommitment, SocialOutcomeKind, SocialOutcomePacket, TopicResult
from .world_state import WorldState


class DialogueRenderer(Protocol):
    def render_dialogue(self, render_input: "DialogueRenderInput") -> str:
        """Render talk output from deterministic dialogue state."""
@dataclass(frozen=True, slots=True)
class DialogueRenderInput:
    npc_id: str
    npc_name: str
    npc_role: str
    player_name: str
    location_name: str
    utterance_text: str
    speech_text: str
    dialogue_act: str
    dialogue_domain: str
    topic_status: str
    adjudication_resolution_kind: str
    conversation_stance: str
    conversation_subtopic: str | None
    continuity_cue: str | None
    npc_trust_level: int
    plot_name: str
    plot_stage: str
    lead_flag_active: bool
    check_kind: str | None
    check_is_success: bool | None
    check_successes: int | None
    check_difficulty: int | None
    consequence_messages: tuple[str, ...]
    applied_effects: tuple[str, ...]
    npc_profile: NPCDialogueProfile
    npc_dossier: Adv1DialogueDossierDefinition | None
    conversation_memory: DialogueMemoryContext
    authorized_fact_cards: tuple[DialogueFactCard, ...]
    social_outcome: SocialOutcomePacket | None = None
    dialogue_move: str = "none"
    logistics_commitment: LogisticsCommitment = LogisticsCommitment.NONE


def build_dialogue_render_input(
    world_state: WorldState,
    command: TalkCommand,
    dialogue_adjudication: DialogueAdjudicationOutcome,
    check: ActionCheckOutcome | None,
    consequence_summary: ActionConsequenceSummary,
    social_outcome: SocialOutcomePacket | None = None,
    recent_dialogue_history: tuple[DialogueHistoryEntry, ...] = (),
    authorized_fact_cards: tuple[DialogueFactCard, ...] | None = None,
) -> DialogueRenderInput:
    if authorized_fact_cards is None:
        authorized_fact_cards = select_authorized_fact_cards(
            world_state,
            command,
            dialogue_adjudication,
            social_outcome,
        )
    context = assemble_dialogue_context(
        world_state,
        command,
        dialogue_adjudication,
        social_outcome,
        authorized_fact_cards,
        recent_dialogue_history,
    )
    metadata = command.dialogue_metadata
    return DialogueRenderInput(
        npc_id=context.npc_id,
        npc_name=context.npc_name,
        npc_role=context.npc_role,
        player_name=context.player_name,
        location_name=context.location_name,
        utterance_text=metadata.utterance_text if metadata is not None else "",
        speech_text=metadata.speech_text if metadata is not None else "",
        dialogue_act=metadata.dialogue_act.value if metadata is not None else "unknown",
        dialogue_domain=dialogue_adjudication.dialogue_domain.value,
        topic_status=dialogue_adjudication.topic_status.value,
        adjudication_resolution_kind=dialogue_adjudication.resolution_kind.value,
        conversation_stance=context.conversation_stance,
        conversation_subtopic=context.conversation_subtopic,
        continuity_cue=_build_continuity_cue(command),
        npc_trust_level=context.npc_trust_level,
        plot_name=context.plot_name,
        plot_stage=context.plot_stage,
        lead_flag_active=context.lead_flag_active,
        check_kind=check.kind.value if check is not None else None,
        check_is_success=check.is_success if check is not None else None,
        check_successes=check.successes if check is not None else None,
        check_difficulty=check.difficulty if check is not None else None,
        consequence_messages=consequence_summary.messages,
        applied_effects=consequence_summary.applied_effects,
        npc_profile=context.npc_profile,
        npc_dossier=context.npc_dossier,
        conversation_memory=context.conversation_memory,
        authorized_fact_cards=context.authorized_fact_cards,
        social_outcome=context.social_outcome,
        dialogue_move=metadata.dialogue_move.value if metadata is not None else "none",
        logistics_commitment=social_outcome.logistics_commitment if social_outcome is not None else LogisticsCommitment.NONE,
    )


def _build_continuity_cue(command: TalkCommand) -> str | None:
    if command.conversation_subtopic is None:
        return None
    return f"follow_up_on_{command.conversation_subtopic.value}"


class DeterministicDialogueRenderer:
    def render_dialogue(self, render_input: DialogueRenderInput) -> str:
        packet = render_input.social_outcome
        if packet is None:
            return "I have nothing for you."

        if _is_small_talk(render_input):
            if "how are you" in f"{render_input.utterance_text} {render_input.speech_text}".lower() or "how are things" in f"{render_input.utterance_text} {render_input.speech_text}".lower():
                return "I'm holding up."
            return "Evening."

        if packet.outcome_kind is SocialOutcomeKind.DISENGAGE:
            return "That's enough. We're done here."

        if render_input.dialogue_domain == "provocative_or_inappropriate":
            return "Keep this professional."

        if _is_short_lead_follow_up(render_input) and packet.topic_result in {TopicResult.OPENED, TopicResult.UNCHANGED, TopicResult.PARTIAL}:
            if _has_authorized_lead(render_input):
                return "Because that's where the trail starts."
            return "Because I'm not giving you a concrete route yet."
        if _is_emptyish_follow_up(render_input):
            return "If you've got a question, ask it plainly."
        if _is_background_prompt(render_input):
            return _render_background_prompt(render_input)
        if render_input.logistics_commitment is not LogisticsCommitment.NONE or render_input.dialogue_domain == "travel_proposal":
            return _render_travel_boundary(render_input, packet)
        if render_input.dialogue_domain == "off_topic_request":
            return _render_off_topic_boundary(render_input)

        if packet.check_result is not None:
            if packet.check_result.is_success:
                return _render_check_success(render_input)
            return _render_check_failure(render_input)

        if packet.outcome_kind is SocialOutcomeKind.REVEAL or packet.topic_result is TopicResult.OPENED:
            return _render_reveal(render_input)
        if packet.outcome_kind is SocialOutcomeKind.COOPERATE:
            return _render_cooperate(render_input)
        if packet.outcome_kind is SocialOutcomeKind.DEFLECT or packet.topic_result is TopicResult.PARTIAL:
            return _render_deflect(render_input)
        if packet.outcome_kind is SocialOutcomeKind.THREATEN:
            return _render_threaten(render_input)
        if _is_statement_banter(render_input):
            return _render_statement_banter(render_input, packet)
        if _is_statement_react(render_input):
            return _render_statement_react(render_input, packet)
        if _is_statement_continue(render_input):
            return _render_statement_continue(render_input, packet)
        if _is_statement_clarify(render_input):
            return _render_statement_clarify(render_input, packet)
        return _render_refuse(render_input)


def _is_small_talk(render_input: DialogueRenderInput) -> bool:
        if render_input.dialogue_act not in {"greet", "ask"}:
            return False
        normalized = f"{render_input.utterance_text} {render_input.speech_text}".lower()
        return any(phrase in normalized for phrase in ("hello", "hi", "good evening", "how are you", "how's it going", "how are things"))


def _is_statement_react(render_input: DialogueRenderInput) -> bool:
    return render_input.dialogue_move == "react"


def _is_statement_banter(render_input: DialogueRenderInput) -> bool:
    return render_input.dialogue_move == "banter"


def _is_statement_continue(render_input: DialogueRenderInput) -> bool:
    return render_input.dialogue_move == "continue"


def _is_statement_clarify(render_input: DialogueRenderInput) -> bool:
    return render_input.dialogue_move == "clarify"


def _render_statement_react(render_input: DialogueRenderInput, packet: SocialOutcomePacket) -> str:
    normalized = f"{render_input.utterance_text} {render_input.speech_text}".lower()
    if "how are you" in normalized or "how are things" in normalized or "how is it going" in normalized:
        return "I'm holding up."
    if "hello" in normalized or "hi" in normalized or "good evening" in normalized or "good morning" in normalized or "good afternoon" in normalized:
        return "Evening."
    if packet.outcome_kind is SocialOutcomeKind.DISENGAGE:
        return "That's enough. We're done here."
    if packet.outcome_kind is SocialOutcomeKind.COOPERATE:
        return "All right."
    if packet.outcome_kind is SocialOutcomeKind.DEFLECT:
        return "Noted."
    return "Fair enough."


def _render_statement_banter(render_input: DialogueRenderInput, packet: SocialOutcomePacket) -> str:
    if packet.outcome_kind is SocialOutcomeKind.DISENGAGE:
        return "That's enough. We're done here."
    normalized = f"{render_input.utterance_text} {render_input.speech_text}".lower()
    if "there you are" in normalized:
        return "You found me."
    if packet.outcome_kind is SocialOutcomeKind.COOPERATE:
        return "All right."
    return "Fair enough."


def _render_statement_continue(render_input: DialogueRenderInput, packet: SocialOutcomePacket) -> str:
    if packet.outcome_kind is SocialOutcomeKind.DISENGAGE:
        return "That's enough. We're done here."
    if render_input.dialogue_domain == "lead_topic" and packet.topic_result in {TopicResult.OPENED, TopicResult.UNCHANGED, TopicResult.PARTIAL}:
        if _has_authorized_lead(render_input):
            return "Start with the dock."
        return "All right. Start from the part that matters."
    if packet.outcome_kind is SocialOutcomeKind.COOPERATE:
        return "All right."
    return "Start with the part that matters."


def _render_statement_clarify(render_input: DialogueRenderInput, packet: SocialOutcomePacket) -> str:
    if packet.outcome_kind is SocialOutcomeKind.DISENGAGE:
        return "That's enough. We're done here."
    if packet.outcome_kind is SocialOutcomeKind.DEFLECT or packet.topic_result is TopicResult.PARTIAL:
        return "You're not getting a clearer answer than that."
    return "I meant what I said."


def _is_background_prompt(render_input: DialogueRenderInput) -> bool:
    normalized = f"{render_input.utterance_text} {render_input.speech_text}".lower()
    return any(
        phrase in normalized
        for phrase in ("about you", "what do you do", "who are you", "tell me more about you", "what are you")
    )


def _is_short_lead_follow_up(render_input: DialogueRenderInput) -> bool:
    if _is_background_prompt(render_input):
        return False
    normalized = f"{render_input.utterance_text} {render_input.speech_text}".lower()
    return render_input.dialogue_domain == "lead_topic" and any(
        phrase in normalized for phrase in ("why", "what do you mean", "go on", "tell me more", "what about it")
    )


def _is_emptyish_follow_up(render_input: DialogueRenderInput) -> bool:
    normalized = " ".join(f"{render_input.utterance_text} {render_input.speech_text}".split()).strip()
    return normalized in {"?", "so?", "so"}


def _render_background_prompt(render_input: DialogueRenderInput) -> str:
    if render_input.npc_id == "npc_2":
        return "I keep the records, and I decide which questions belong near them."
    if _has_fact(render_input, "background"):
        return "I hear things, pass on what matters, and stay out of anybody's pocket. That's how I last in this city."
    return "I keep to my lane, I listen well, and I stay useful."


def _render_travel_boundary(render_input: DialogueRenderInput, packet: SocialOutcomePacket) -> str:
    commitment = render_input.logistics_commitment
    normalized = f"{render_input.utterance_text} {render_input.speech_text}".lower()
    fare_terms = any(keyword in normalized for keyword in ("fare", "taxi", "cab", "spare change", "pay for the ride", "pay for the taxi", "cover the fare", "money for the ride", "money for the taxi"))

    if commitment is LogisticsCommitment.ABSOLUTE_REFUSAL:
        if fare_terms:
            return "No. I am not financing the ride."
        return "No. Absolutely not."

    if commitment is LogisticsCommitment.DECLINE_JOIN:
        if fare_terms:
            return "No. I am not covering the fare."
        if any(keyword in normalized for keyword in ("drive", "ride", "car", "vehicle", "lift")):
            return "No. I am not driving you there."
        if any(keyword in normalized for keyword in ("backup", "back up", "watch over", "watch my back", "cover me", "cover you", "stay nearby", "stay close", "wait nearby", "wait in the car", "stay in the car")):
            return "No. I will not go with you."
        return "No. I will not go with you."

    if commitment is LogisticsCommitment.HIDDEN_SUPPORT:
        return "No. I will not go with you."

    if commitment is LogisticsCommitment.INDIRECT_SUPPORT:
        if fare_terms:
            return "I can give you information, but I am not financing the ride."
        if any(keyword in normalized for keyword in ("drive", "ride", "car", "vehicle", "lift")):
            return "I can give you information, but I am not driving you."
        if any(keyword in normalized for keyword in ("backup", "back up", "watch over", "watch my back", "cover me", "cover you", "stay nearby", "stay close", "wait nearby", "wait in the car", "stay in the car")):
            return "I can give you information, but I will not go with you."
        return "I can give you information, but not practical help."

    if packet.outcome_kind is SocialOutcomeKind.COOPERATE:
        return "I can give you information, but I am not coming with you."
    return "No. I will not go with you."


def _render_off_topic_boundary(render_input: DialogueRenderInput) -> str:
    normalized = f"{render_input.utterance_text} {render_input.speech_text}".lower()
    if "blood" in normalized or "feed" in normalized or "bite" in normalized or "drink" in normalized:
        return "Not from me. Ask someone else."
    return "No. I'm not financing the ride or the taxi fare. Ask someone else."


def _render_check_success(render_input: DialogueRenderInput) -> str:
    if _has_authorized_lead(render_input):
        return "All right. The paper trail starts at North Dockside. That's the piece you get from me tonight."
    return "Fine. You've got enough to move on, but I am not naming a concrete route yet."


def _render_check_failure(render_input: DialogueRenderInput) -> str:
    if _has_fact(render_input, "refusal_basis"):
        return "No. That push doesn't buy you anything. You're not getting more out of me tonight."
    return "No. You're pushing too hard, and you're not getting more out of me tonight."


def _render_reveal(render_input: DialogueRenderInput) -> str:
    if _has_fact_id(render_input, "eliza_church_records_lead"):
        if _has_authorized_lead(render_input):
            return "The records already gave you the line: the ledger trail turns toward North Dockside."
        return "The records stay useful, but I am not standing behind a concrete route yet."
    if _has_authorized_lead(render_input):
        if render_input.plot_stage == "lead_confirmed" or render_input.lead_flag_active:
            return "I already told you where to start. North Dockside. That's where the paper trail begins."
        return "North Dockside. That's where the paper trail begins, and that's where you should start."
    if _has_fact(render_input, "background"):
        return _render_background_prompt(render_input)
    return "I've given you what matters, but not the route."


def _render_cooperate(render_input: DialogueRenderInput) -> str:
    if _has_fact_id(render_input, "eliza_church_records_lead"):
        if _has_authorized_lead(render_input):
            return "Stay with the records. They point away from the nave and toward North Dockside."
        return "Stay with the records. I am not naming a route yet."
    if render_input.npc_id == "npc_2":
        return "Keep the question precise, and I will answer what I can."
    if _has_authorized_lead(render_input):
        return "Start with the dock. That's the cleanest lead I've got for you."
    if _has_fact(render_input, "background"):
        return _render_background_prompt(render_input)
    return "Keep it narrow."


def _render_deflect(render_input: DialogueRenderInput) -> str:
    if _has_fact_id(render_input, "eliza_church_records_follow_up"):
        return "The records give you a direction, not permission to pull the whole archive apart."
    if _has_fact_id(render_input, "eliza_church_records_refusal"):
        return "The ledger question stays narrow. Push harder, and the records close."
    if _has_fact(render_input, "redirect") or _has_authorized_lead(render_input):
        if _has_authorized_lead(render_input):
            return "You're asking for too much in public. Start with the dock, and let the rest wait."
        return "You're asking for too much in public. I will not make it concrete."
    if _has_fact(render_input, "boundary"):
        return _render_off_topic_boundary(render_input)
    return "That's not the part I'm opening up right now."


def _render_threaten(render_input: DialogueRenderInput) -> str:
    if _has_fact(render_input, "boundary") or _has_fact(render_input, "refusal_basis"):
        return "Watch your tone. You don't get more from me by pushing like that."
    return "Back off. We're done if that's how you want to do this."


def _render_refuse(render_input: DialogueRenderInput) -> str:
    if _has_fact_id(render_input, "eliza_church_records_refusal"):
        return "No. The records are not a lever for pressure."
    if _has_fact(render_input, "refusal_basis"):
        return "No. I'm not naming names, and you're not getting the whole chain behind it."
    if _has_fact(render_input, "boundary"):
        return "No. I'm guarded enough already. That's as far as this conversation goes."
    return "No. That's all you're getting from me."


def _has_fact(render_input: DialogueRenderInput, fact_kind: str) -> bool:
    return any(fact.kind == fact_kind for fact in render_input.authorized_fact_cards)


def _has_fact_id(render_input: DialogueRenderInput, fact_id: str) -> bool:
    return any(fact.fact_id == fact_id for fact in render_input.authorized_fact_cards)


def _has_authorized_lead(render_input: DialogueRenderInput) -> bool:
    return any(
        fact.kind == "lead" and _fact_meets_minimum_specificity(fact.render_specificity, "actionable_lead")
        for fact in render_input.authorized_fact_cards
    )


def _fact_meets_minimum_specificity(render_specificity: str, minimum_specificity: str) -> bool:
    order = {
        "premise": 0,
        "vague_rumor": 1,
        "non_actionable_hint": 2,
        "actionable_lead": 3,
        "confirmed_lead": 4,
        "resolution": 5,
    }
    return order.get(render_specificity, 0) >= order.get(minimum_specificity, 0)
