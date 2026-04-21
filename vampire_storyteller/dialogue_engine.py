from __future__ import annotations

from dataclasses import dataclass

from .adventure_loader import Adv1DialogueHookDefinition, load_adv1_dialogue_hook_definitions, load_adv1_plot_progression_rules
from .command_models import ConversationStance, DialogueAct, DialogueMetadata
from .dialogue_adjudication import DialogueTopicStatus
from .dialogue_domain import DialogueDomain, classify_dialogue_domain
from .dialogue_subtopic import DialogueSubtopic
from .social_models import SocialOutcomePacket
from .world_state import WorldState


@dataclass(frozen=True, slots=True)
class DialogueResolutionResult:
    output_text: str
    conversation_focus_npc_id: str | None
    conversation_stance: ConversationStance
    social_outcome: SocialOutcomePacket | None = None


def resolve_talk(
    world_state: WorldState,
    npc_id: str,
    dialogue_metadata: DialogueMetadata | None,
    conversation_stance: ConversationStance = ConversationStance.NEUTRAL,
) -> str:
    return resolve_talk_result(world_state, npc_id, dialogue_metadata, conversation_stance).output_text


def resolve_talk_result(
    world_state: WorldState,
    npc_id: str,
    dialogue_metadata: DialogueMetadata | None,
    conversation_stance: ConversationStance = ConversationStance.NEUTRAL,
    dialogue_domain: DialogueDomain | None = None,
    active_subtopic: DialogueSubtopic | None = None,
    social_outcome: SocialOutcomePacket | None = None,
) -> DialogueResolutionResult:
    npc = world_state.npcs.get(npc_id)
    if npc is None:
        return DialogueResolutionResult(
            output_text=f"Talk is blocked: no NPC with id '{npc_id}' exists.",
            conversation_focus_npc_id=None,
            conversation_stance=conversation_stance,
            social_outcome=social_outcome,
        )

    if npc.location_id != world_state.player.location_id:
        location = world_state.locations.get(world_state.player.location_id or "")
        location_name = location.name if location is not None else (world_state.player.location_id or "unknown location")
        return DialogueResolutionResult(
            output_text=f"Talk is blocked: {npc.name} is not present at {location_name}.",
            conversation_focus_npc_id=None,
            conversation_stance=conversation_stance,
            social_outcome=social_outcome,
        )

    resolved_domain = dialogue_domain or classify_dialogue_domain(
        world_state,
        npc_id,
        dialogue_metadata,
        DialogueTopicStatus.UNKNOWN,
        conversation_stance,
        active_subtopic,
    )
    output_text = _system_feedback_for_non_renderable_case(world_state, npc.id, dialogue_metadata, resolved_domain)
    _apply_dialogue_progression_hooks(world_state, npc, dialogue_metadata, conversation_stance, resolved_domain)
    next_stance = _resolve_next_conversation_stance(conversation_stance, dialogue_metadata, social_outcome)
    return DialogueResolutionResult(
        output_text=output_text,
        conversation_focus_npc_id=npc.id,
        conversation_stance=next_stance,
        social_outcome=social_outcome,
    )


def _system_feedback_for_non_renderable_case(
    world_state: WorldState,
    npc_id: str,
    dialogue_metadata: DialogueMetadata | None,
    dialogue_domain: DialogueDomain,
) -> str:
    if dialogue_metadata is not None:
        return ""
    npc = world_state.npcs.get(npc_id)
    if npc is None:
        return ""
    plot_rules = load_adv1_plot_progression_rules()
    plot = world_state.plots.get(plot_rules.plot_id)
    current_stage = plot.stage if plot is not None else ""
    hooks = load_adv1_dialogue_hook_definitions()
    hook = _find_dialogue_hook(hooks, npc, current_stage, None, ConversationStance.NEUTRAL, plot_rules.plot_id)
    if hook is None and dialogue_domain is DialogueDomain.LEAD_TOPIC:
        return f"Talk is blocked: {npc.name} has said what he will say for now."
    return ""


def _apply_dialogue_progression_hooks(
    world_state: WorldState,
    npc,
    dialogue_metadata: DialogueMetadata | None,
    conversation_stance: ConversationStance,
    dialogue_domain: DialogueDomain,
) -> None:
    if dialogue_domain is not DialogueDomain.LEAD_TOPIC:
        return
    plot_rules = load_adv1_plot_progression_rules()
    plot = world_state.plots.get(plot_rules.plot_id)
    current_stage = plot.stage if plot is not None else ""
    hooks = load_adv1_dialogue_hook_definitions()
    dialogue_act = dialogue_metadata.dialogue_act if dialogue_metadata is not None else None
    hook = _find_dialogue_hook(hooks, npc, current_stage, dialogue_act, conversation_stance, plot_rules.plot_id)
    if hook is None:
        return
    if hook.trust_delta != 0:
        _adjust_npc_trust(world_state, npc.id, hook.trust_delta)
    for story_flag in hook.story_flags_to_add:
        world_state.add_story_flag(story_flag)
    if not hook.repeatable:
        _mark_dialogue_hook_consumed(world_state, npc.id, hook.hook_id)


def _resolve_next_conversation_stance(
    conversation_stance: ConversationStance,
    dialogue_metadata: DialogueMetadata | None,
    social_outcome: SocialOutcomePacket | None,
) -> ConversationStance:
    if social_outcome is not None:
        return social_outcome.stance_shift.to_stance
    dialogue_act = dialogue_metadata.dialogue_act if dialogue_metadata is not None else None
    if dialogue_act in (DialogueAct.ACCUSE, DialogueAct.THREATEN):
        return ConversationStance.GUARDED
    return conversation_stance


def _find_dialogue_hook(
    hooks: list[Adv1DialogueHookDefinition],
    npc,
    plot_stage: str,
    dialogue_act: DialogueAct | None,
    conversation_stance: ConversationStance,
    plot_id: str,
) -> Adv1DialogueHookDefinition | None:
    matching_hooks = [
        hook
        for hook in hooks
        if hook.npc_id == npc.id
        and hook.required_plot_id == plot_id
        and hook.required_plot_stage == plot_stage
        and hook.minimum_trust_level <= npc.trust_level
        and (hook.repeatable or hook.hook_id not in npc.consumed_dialogue_hooks)
    ]
    if not matching_hooks:
        return None

    if dialogue_act in (DialogueAct.ACCUSE, DialogueAct.THREATEN):
        return _select_best_hook_for_act(matching_hooks, dialogue_act)

    if conversation_stance is ConversationStance.GUARDED:
        if dialogue_act is None:
            return None
        return _select_best_hook_for_act(matching_hooks, dialogue_act)

    if dialogue_act is not None:
        matched_hook = _select_best_hook_for_act(matching_hooks, dialogue_act)
        if matched_hook is not None:
            return matched_hook

    return _select_best_generic_hook(matching_hooks)


def _select_best_hook_for_act(hooks: list[Adv1DialogueHookDefinition], dialogue_act: DialogueAct) -> Adv1DialogueHookDefinition | None:
    act_specific_hooks = [hook for hook in hooks if dialogue_act.value in hook.required_dialogue_acts]
    if not act_specific_hooks:
        return None
    return max(act_specific_hooks, key=lambda hook: (hook.minimum_trust_level, len(hook.required_dialogue_acts), hook.repeatable))


def _select_best_generic_hook(hooks: list[Adv1DialogueHookDefinition]) -> Adv1DialogueHookDefinition | None:
    generic_hooks = [hook for hook in hooks if not hook.required_dialogue_acts]
    if not generic_hooks:
        return None
    return max(generic_hooks, key=lambda hook: (hook.minimum_trust_level, hook.repeatable))


def _adjust_npc_trust(world_state: WorldState, npc_id: str, delta: int) -> None:
    if delta == 0:
        return
    npc = world_state.npcs.get(npc_id)
    if npc is None:
        return
    npc.social_state.trust = max(0, npc.social_state.trust + delta)
    npc.trust_level = npc.social_state.trust


def _mark_dialogue_hook_consumed(world_state: WorldState, npc_id: str, hook_id: str) -> None:
    npc = world_state.npcs.get(npc_id)
    if npc is None:
        return
    if hook_id not in npc.consumed_dialogue_hooks:
        npc.consumed_dialogue_hooks.append(hook_id)
