from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .action_resolution import ActionCheckOutcome, ActionConsequenceSummary
from .adventure_loader import load_adv1_dialogue_fact_definitions, load_adv1_plot_progression_rules
from .command_models import TalkCommand
from .dialogue_adjudication import DialogueAdjudicationOutcome
from .models import NPCDialogueProfile
from .world_state import WorldState
from .social_models import SocialOutcomeKind, SocialOutcomePacket, TopicResult


class DialogueRenderer(Protocol):
    def render_dialogue(self, render_input: "DialogueRenderInput") -> str:
        """Render talk output from deterministic dialogue state."""


@dataclass(frozen=True, slots=True)
class DialogueFactCard:
    fact_id: str
    kind: str
    summary: str


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
    authorized_fact_cards: tuple[DialogueFactCard, ...]
    social_outcome: SocialOutcomePacket | None = None


def build_dialogue_render_input(
    world_state: WorldState,
    command: TalkCommand,
    dialogue_adjudication: DialogueAdjudicationOutcome,
    check: ActionCheckOutcome | None,
    consequence_summary: ActionConsequenceSummary,
    social_outcome: SocialOutcomePacket | None = None,
) -> DialogueRenderInput:
    npc = world_state.npcs.get(command.npc_id)
    if npc is None:
        raise RuntimeError(f"npc '{command.npc_id}' is missing")

    metadata = command.dialogue_metadata
    plot_rules = load_adv1_plot_progression_rules()
    plot = world_state.plots.get(plot_rules.plot_id)
    location = world_state.locations.get(world_state.player.location_id or "")
    location_name = location.name if location is not None else (world_state.player.location_id or "unknown location")
    authorized_fact_cards = _select_authorized_fact_cards(
        world_state,
        command,
        dialogue_adjudication,
        social_outcome,
    )
    return DialogueRenderInput(
        npc_id=npc.id,
        npc_name=npc.name,
        npc_role=npc.role,
        player_name=world_state.player.name,
        location_name=location_name,
        utterance_text=metadata.utterance_text if metadata is not None else "",
        speech_text=metadata.speech_text if metadata is not None else "",
        dialogue_act=metadata.dialogue_act.value if metadata is not None else "unknown",
        dialogue_domain=dialogue_adjudication.dialogue_domain.value,
        topic_status=dialogue_adjudication.topic_status.value,
        adjudication_resolution_kind=dialogue_adjudication.resolution_kind.value,
        conversation_stance=dialogue_adjudication.conversation_stance.value,
        conversation_subtopic=command.conversation_subtopic.value if command.conversation_subtopic is not None else None,
        continuity_cue=_build_continuity_cue(command),
        npc_trust_level=npc.trust_level,
        plot_name=plot.name if plot is not None else plot_rules.plot_id,
        plot_stage=plot.stage if plot is not None else "",
        lead_flag_active=plot_rules.talk_required_story_flag in set(world_state.story_flags),
        check_kind=check.kind.value if check is not None else None,
        check_is_success=check.is_success if check is not None else None,
        check_successes=check.successes if check is not None else None,
        check_difficulty=check.difficulty if check is not None else None,
        consequence_messages=consequence_summary.messages,
        applied_effects=consequence_summary.applied_effects,
        npc_profile=npc.dialogue_profile,
        authorized_fact_cards=authorized_fact_cards,
        social_outcome=social_outcome,
    )


def _build_continuity_cue(command: TalkCommand) -> str | None:
    if command.conversation_subtopic is None:
        return None
    return f"follow_up_on_{command.conversation_subtopic.value}"


def _select_authorized_fact_cards(
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
        selected.append(DialogueFactCard(fact_id=fact.fact_id, kind=fact.kind, summary=fact.summary))

    return tuple(selected)


def _normalize_text(metadata) -> str:
    if metadata is None:
        return ""
    return " ".join(
        piece.lower().replace("-", " ")
        for piece in (metadata.utterance_text, metadata.speech_text, metadata.topic or "")
        if piece
    )


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
            return True
        return any(keyword in normalized_text for keyword in ("dock", "docks", "ledger", "paper trail", "waterline"))
    return False


class DeterministicDialogueRenderer:
    def render_dialogue(self, render_input: DialogueRenderInput) -> str:
        packet = render_input.social_outcome
        if packet is None:
            return f"{render_input.npc_name} gives you a brief, unreadable look and says nothing useful."

        if _is_small_talk(render_input):
            if "how are you" in f"{render_input.utterance_text} {render_input.speech_text}".lower() or "how are things" in f"{render_input.utterance_text} {render_input.speech_text}".lower():
                return (
                    f"{render_input.npc_name} gives a short shrug. "
                    "'I'm holding up. You needed something specific?'"
                )
            return f"{render_input.npc_name} gives a brief nod and keeps the greeting polite."

        if packet.outcome_kind is SocialOutcomeKind.DISENGAGE:
            return f"{render_input.npc_name} closes off the exchange and leaves you with no easy way to continue."

        if render_input.dialogue_domain == "provocative_or_inappropriate":
            return f"{render_input.npc_name}'s expression hardens. 'Keep this professional.'"

        if _is_short_lead_follow_up(render_input) and packet.topic_result in {TopicResult.OPENED, TopicResult.UNCHANGED, TopicResult.PARTIAL}:
            return f"{render_input.npc_name} keeps his voice low. 'Because that's where the trail starts.'"

        intro = _build_intro(render_input)
        fact_text = _build_fact_text(render_input.authorized_fact_cards)

        if render_input.dialogue_domain == "travel_proposal" and fact_text:
            return f"{intro} {render_input.npc_name} keeps the request at arm's length. {fact_text}"
        if render_input.dialogue_domain == "off_topic_request" and fact_text:
            return f"{intro} {render_input.npc_name} redirects the conversation away from the favor. {fact_text}"

        if packet.check_result is not None:
            if packet.check_result.is_success:
                opening = f"{intro} The pressure lands, and {render_input.npc_name} finally gives you something solid."
            else:
                opening = f"{intro} The pressure does not land, and {render_input.npc_name} stays guarded and gives nothing away."
        elif packet.outcome_kind is SocialOutcomeKind.REVEAL or packet.topic_result is TopicResult.OPENED:
            lead_shift = " He loosens his shoulders just enough for the change to show." if render_input.lead_flag_active or render_input.plot_stage == "lead_confirmed" else ""
            opening = f"{render_input.npc_name} keeps his voice low and gives you a clearer answer.{lead_shift}"
        elif packet.outcome_kind is SocialOutcomeKind.COOPERATE:
            opening = f"{intro} {render_input.npc_name} stays conversational without opening too much."
        elif packet.outcome_kind is SocialOutcomeKind.DEFLECT:
            opening = f"{intro} {render_input.npc_name} answers narrowly, then redirects the conversation."
        elif packet.outcome_kind is SocialOutcomeKind.THREATEN:
            opening = f"{intro} {render_input.npc_name} stays guarded and lets the warning hang there."
        else:
            opening = f"{intro} {render_input.npc_name} stays guarded and keeps the topic closed."

        if _is_background_prompt(render_input) and fact_text:
            return f"{opening} {fact_text}"

        if packet.outcome_kind is SocialOutcomeKind.THREATEN and fact_text:
            return f"{opening} {fact_text}"
        if packet.outcome_kind is SocialOutcomeKind.REFUSE and fact_text:
            return f"{opening} {fact_text}"
        if packet.outcome_kind is SocialOutcomeKind.DEFLECT and fact_text:
            return f"{opening} {fact_text}"
        if (packet.outcome_kind is SocialOutcomeKind.REVEAL or packet.topic_result is TopicResult.OPENED) and fact_text:
            return f"{opening} {fact_text}"
        if packet.topic_result is TopicResult.PARTIAL and fact_text:
            return f"{opening} {fact_text}"
        if fact_text:
            return f"{opening} {fact_text}"

        return opening


def _build_intro(render_input: DialogueRenderInput) -> str:
    persona = render_input.npc_profile.public_persona or f"a {render_input.npc_role.lower()}"
    speaking_style = render_input.npc_profile.speaking_style or "careful"
    return f"{render_input.npc_name} responds in a {speaking_style} way, still presenting as {persona}."


def _build_fact_text(facts: tuple[DialogueFactCard, ...]) -> str:
    if not facts:
        return ""
    summaries = [fact.summary.rstrip(".") for fact in facts[:2]]
    if len(summaries) == 1:
        return f"{summaries[0]}."
    return f"{summaries[0]}. {summaries[1]}."


def _is_small_talk(render_input: DialogueRenderInput) -> bool:
    if render_input.dialogue_act not in {"greet", "ask"}:
        return False
    normalized = f"{render_input.utterance_text} {render_input.speech_text}".lower()
    return any(phrase in normalized for phrase in ("hello", "hi", "good evening", "how are you", "how's it going", "how are things"))


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
