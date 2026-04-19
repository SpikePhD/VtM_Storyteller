from __future__ import annotations

from dataclasses import dataclass

from .adventure_loader import (
    Adv1DialogueHookDefinition,
    load_adv1_dialogue_hook_definitions,
    load_adv1_plot_progression_rules,
)
from .command_models import ConversationStance, DialogueAct, DialogueMetadata
from .world_state import WorldState


@dataclass(frozen=True, slots=True)
class DialogueResolutionResult:
    output_text: str
    conversation_focus_npc_id: str | None
    conversation_stance: ConversationStance


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
) -> DialogueResolutionResult:
    npc = world_state.npcs.get(npc_id)
    if npc is None:
        return DialogueResolutionResult(
            output_text=f"Talk is blocked: no NPC with id '{npc_id}' exists.",
            conversation_focus_npc_id=None,
            conversation_stance=conversation_stance,
        )

    if npc.location_id != world_state.player.location_id:
        location = world_state.locations.get(world_state.player.location_id or "")
        location_name = location.name if location is not None else (world_state.player.location_id or "unknown location")
        return DialogueResolutionResult(
            output_text=f"Talk is blocked: {npc.name} is not present at {location_name}.",
            conversation_focus_npc_id=None,
            conversation_stance=conversation_stance,
        )

    plot_rules = load_adv1_plot_progression_rules()
    plot = world_state.plots.get(plot_rules.plot_id)
    current_stage = plot.stage if plot is not None else ""
    hooks = load_adv1_dialogue_hook_definitions()
    dialogue_act = dialogue_metadata.dialogue_act if dialogue_metadata is not None else None
    hook = _find_dialogue_hook(hooks, npc, current_stage, dialogue_act, conversation_stance, plot_rules.plot_id)
    if hook is not None:
        if hook.trust_delta != 0:
            _adjust_npc_trust(world_state, npc_id, hook.trust_delta)
        for story_flag in hook.story_flags_to_add:
            world_state.add_story_flag(story_flag)
        if not hook.repeatable:
            _mark_dialogue_hook_consumed(world_state, npc_id, hook.hook_id)
        response_text = hook.blocked_text if _should_use_blocked_text(hook, dialogue_metadata) else hook.dialogue_text
        next_stance = _next_conversation_stance(dialogue_act, response_text == hook.blocked_text)
        return DialogueResolutionResult(
            output_text=_render_dialogue_text(response_text, npc.name, dialogue_metadata),
            conversation_focus_npc_id=npc_id,
            conversation_stance=next_stance,
        )

    fallback = _find_dialogue_fallback(hooks, npc, current_stage, plot_rules.plot_id)
    if fallback is not None:
        next_stance = ConversationStance.GUARDED if conversation_stance == ConversationStance.GUARDED or dialogue_act in (DialogueAct.ACCUSE, DialogueAct.THREATEN) else ConversationStance.NEUTRAL
        return DialogueResolutionResult(
            output_text=_render_dialogue_text(f"Talk is blocked: {fallback}", npc.name, dialogue_metadata),
            conversation_focus_npc_id=npc_id,
            conversation_stance=next_stance,
        )

    return DialogueResolutionResult(
        output_text=f"{npc.name} has nothing useful to say right now.",
        conversation_focus_npc_id=npc_id,
        conversation_stance=conversation_stance,
    )


def _find_dialogue_hook(
    hooks,
    npc,
    plot_stage: str,
    dialogue_act: DialogueAct | None,
    conversation_stance: ConversationStance,
    plot_id: str,
):
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
        guarded_hook = _select_best_hook_for_act(matching_hooks, dialogue_act)
        if guarded_hook is not None:
            return guarded_hook
        return None

    if conversation_stance == ConversationStance.GUARDED:
        if dialogue_act is not None:
            matched_hook = _select_best_hook_for_act(matching_hooks, dialogue_act)
            if matched_hook is not None:
                return matched_hook
        return None

    if dialogue_act is not None:
        matched_hook = _select_best_hook_for_act(matching_hooks, dialogue_act)
        if matched_hook is not None:
            return matched_hook

    return _select_best_generic_hook(matching_hooks)


def _select_best_hook_for_act(hooks, dialogue_act: DialogueAct) -> Adv1DialogueHookDefinition | None:
    act_specific_hooks = [hook for hook in hooks if dialogue_act.value in hook.required_dialogue_acts]
    if not act_specific_hooks:
        return None
    return max(act_specific_hooks, key=lambda hook: (hook.minimum_trust_level, len(hook.required_dialogue_acts), hook.repeatable))


def _select_best_generic_hook(hooks) -> Adv1DialogueHookDefinition | None:
    generic_hooks = [hook for hook in hooks if not hook.required_dialogue_acts]
    if not generic_hooks:
        return None
    return max(generic_hooks, key=lambda hook: (hook.minimum_trust_level, hook.repeatable))


def _next_conversation_stance(dialogue_act: DialogueAct | None, used_blocked_text: bool) -> ConversationStance:
    if used_blocked_text:
        return ConversationStance.GUARDED
    if dialogue_act in (DialogueAct.ACCUSE, DialogueAct.THREATEN):
        return ConversationStance.GUARDED
    return ConversationStance.NEUTRAL


def _adjust_npc_trust(world_state: WorldState, npc_id: str, delta: int) -> None:
    if delta == 0:
        return
    npc = world_state.npcs.get(npc_id)
    if npc is None:
        return
    npc.trust_level = max(0, npc.trust_level + delta)


def _mark_dialogue_hook_consumed(world_state: WorldState, npc_id: str, hook_id: str) -> None:
    npc = world_state.npcs.get(npc_id)
    if npc is None:
        return
    if hook_id not in npc.consumed_dialogue_hooks:
        npc.consumed_dialogue_hooks.append(hook_id)


def _find_dialogue_fallback(hooks, npc, plot_stage: str, plot_id: str) -> str | None:
    for hook in hooks:
        if hook.npc_id == npc.id and hook.required_plot_id == plot_id and hook.required_plot_stage == plot_stage:
            return hook.blocked_text
    for hook in hooks:
        if hook.npc_id == npc.id:
            return hook.blocked_text
    return None


def _should_use_blocked_text(hook: Adv1DialogueHookDefinition, dialogue_metadata: DialogueMetadata | None) -> bool:
    if dialogue_metadata is None:
        return False
    if dialogue_metadata.dialogue_act not in (DialogueAct.ACCUSE, DialogueAct.THREATEN):
        return False
    return dialogue_metadata.dialogue_act.value in hook.required_dialogue_acts and bool(hook.blocked_text)


def _render_dialogue_text(template: str, npc_name: str, dialogue_metadata: DialogueMetadata | None) -> str:
    if dialogue_metadata is None:
        return template

    class _SafeTemplateDict(dict[str, str]):
        def __missing__(self, key: str) -> str:
            return "{" + key + "}"

    values = _SafeTemplateDict(
        npc_name=npc_name,
        utterance_text=dialogue_metadata.utterance_text,
        speech_text=dialogue_metadata.speech_text,
        dialogue_act=dialogue_metadata.dialogue_act.value,
    )
    return template.format_map(values)
