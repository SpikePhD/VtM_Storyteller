from __future__ import annotations

from .adventure_loader import Adv1DialogueHookDefinition, load_adv1_dialogue_hook_definitions
from .command_models import DialogueAct, DialogueMetadata
from .world_state import WorldState


def resolve_talk(world_state: WorldState, npc_id: str, dialogue_metadata: DialogueMetadata | None) -> str:
    npc = world_state.npcs.get(npc_id)
    if npc is None:
        return f"Talk is blocked: no NPC with id '{npc_id}' exists."

    if npc.location_id != world_state.player.location_id:
        location = world_state.locations.get(world_state.player.location_id or "")
        location_name = location.name if location is not None else (world_state.player.location_id or "unknown location")
        return f"Talk is blocked: {npc.name} is not present at {location_name}."

    plot = world_state.plots.get("plot_1")
    current_stage = plot.stage if plot is not None else ""
    hooks = load_adv1_dialogue_hook_definitions()
    hook = _find_dialogue_hook(hooks, npc, current_stage, dialogue_metadata.dialogue_act if dialogue_metadata is not None else None)
    if hook is not None:
        if hook.trust_delta != 0:
            _adjust_npc_trust(world_state, npc_id, hook.trust_delta)
        for story_flag in hook.story_flags_to_add:
            world_state.add_story_flag(story_flag)
        if not hook.repeatable:
            _mark_dialogue_hook_consumed(world_state, npc_id, hook.hook_id)
        response_text = hook.blocked_text if _should_use_blocked_text(hook, dialogue_metadata) else hook.dialogue_text
        return _render_dialogue_text(response_text, npc.name, dialogue_metadata)

    fallback = _find_dialogue_fallback(hooks, npc, current_stage)
    if fallback is not None:
        return _render_dialogue_text(f"Talk is blocked: {fallback}", npc.name, dialogue_metadata)

    return f"{npc.name} has nothing useful to say right now."


def _find_dialogue_hook(hooks, npc, plot_stage: str, dialogue_act: DialogueAct | None):
    matching_hook = None
    matching_trust_level = -1
    for hook in hooks:
        if hook.npc_id != npc.id or hook.required_plot_id != "plot_1" or hook.required_plot_stage != plot_stage:
            continue
        if hook.minimum_trust_level > npc.trust_level:
            continue
        if not hook.repeatable and hook.hook_id in npc.consumed_dialogue_hooks:
            continue
        if hook.minimum_trust_level > matching_trust_level:
            matching_hook = hook
            matching_trust_level = hook.minimum_trust_level
            continue
        if hook.minimum_trust_level == matching_trust_level and dialogue_act is not None:
            if hook.required_dialogue_acts and dialogue_act.value not in hook.required_dialogue_acts:
                continue
            if matching_hook is None:
                matching_hook = hook
                continue
            if _hook_specificity_score(hook, dialogue_act) > _hook_specificity_score(matching_hook, dialogue_act):
                matching_hook = hook
    return matching_hook


def _hook_specificity_score(hook: Adv1DialogueHookDefinition, dialogue_act: DialogueAct) -> tuple[int, int]:
    matches_act = 1 if hook.required_dialogue_acts and dialogue_act.value in hook.required_dialogue_acts else 0
    any_specificity = 1 if hook.required_dialogue_acts else 0
    return (matches_act, any_specificity)


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


def _find_dialogue_fallback(hooks, npc, plot_stage: str) -> str | None:
    for hook in hooks:
        if hook.npc_id == npc.id and hook.required_plot_id == "plot_1" and hook.required_plot_stage == plot_stage:
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
