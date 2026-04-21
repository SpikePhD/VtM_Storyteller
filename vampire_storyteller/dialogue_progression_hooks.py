from __future__ import annotations

from .adventure_loader import Adv1DialogueHookDefinition, load_adv1_dialogue_hook_definitions, load_adv1_plot_progression_rules
from .command_models import ConversationStance, DialogueAct, DialogueMetadata
from .world_state import WorldState


def apply_dialogue_progression_hooks(
    world_state: WorldState,
    npc,
    dialogue_metadata: DialogueMetadata | None,
    conversation_stance: ConversationStance,
    dialogue_domain,
) -> None:
    if dialogue_domain.value != "lead_topic":
        return
    plot_rules = load_adv1_plot_progression_rules()
    plot = world_state.plots.get(plot_rules.plot_id)
    current_stage = plot.stage if plot is not None else ""
    hooks = load_adv1_dialogue_hook_definitions()
    dialogue_act = dialogue_metadata.dialogue_act if dialogue_metadata is not None else None
    hook = find_dialogue_hook(hooks, npc, current_stage, dialogue_act, conversation_stance, plot_rules.plot_id)
    if hook is None:
        return
    if hook.trust_delta != 0:
        adjust_npc_trust(world_state, npc.id, hook.trust_delta)
    for story_flag in hook.story_flags_to_add:
        world_state.add_story_flag(story_flag)
    if not hook.repeatable:
        mark_dialogue_hook_consumed(world_state, npc.id, hook.hook_id)


def find_dialogue_hook(
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
        return select_best_hook_for_act(matching_hooks, dialogue_act)

    if conversation_stance is ConversationStance.GUARDED:
        if dialogue_act is None:
            return None
        return select_best_hook_for_act(matching_hooks, dialogue_act)

    if dialogue_act is not None:
        matched_hook = select_best_hook_for_act(matching_hooks, dialogue_act)
        if matched_hook is not None:
            return matched_hook

    return select_best_generic_hook(matching_hooks)


def select_best_hook_for_act(hooks: list[Adv1DialogueHookDefinition], dialogue_act: DialogueAct) -> Adv1DialogueHookDefinition | None:
    act_specific_hooks = [hook for hook in hooks if dialogue_act.value in hook.required_dialogue_acts]
    if not act_specific_hooks:
        return None
    return max(act_specific_hooks, key=lambda hook: (hook.minimum_trust_level, len(hook.required_dialogue_acts), hook.repeatable))


def select_best_generic_hook(hooks: list[Adv1DialogueHookDefinition]) -> Adv1DialogueHookDefinition | None:
    generic_hooks = [hook for hook in hooks if not hook.required_dialogue_acts]
    if not generic_hooks:
        return None
    return max(generic_hooks, key=lambda hook: (hook.minimum_trust_level, hook.repeatable))


def adjust_npc_trust(world_state: WorldState, npc_id: str, delta: int) -> None:
    if delta == 0:
        return
    npc = world_state.npcs.get(npc_id)
    if npc is None:
        return
    npc.social_state.trust = max(0, npc.social_state.trust + delta)
    npc.trust_level = npc.social_state.trust


def mark_dialogue_hook_consumed(world_state: WorldState, npc_id: str, hook_id: str) -> None:
    npc = world_state.npcs.get(npc_id)
    if npc is None:
        return
    if hook_id not in npc.consumed_dialogue_hooks:
        npc.consumed_dialogue_hooks.append(hook_id)
