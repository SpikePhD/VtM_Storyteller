from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .action_resolution import ActionCheckOutcome, ActionConsequenceSummary
from .adventure_loader import load_adv1_plot_progression_rules
from .command_models import TalkCommand
from .dialogue_adjudication import DialogueAdjudicationOutcome
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


def build_dialogue_render_input(
    world_state: WorldState,
    command: TalkCommand,
    dialogue_adjudication: DialogueAdjudicationOutcome,
    check: ActionCheckOutcome | None,
    consequence_summary: ActionConsequenceSummary,
) -> DialogueRenderInput:
    npc = world_state.npcs.get(command.npc_id)
    if npc is None:
        raise RuntimeError(f"npc '{command.npc_id}' is missing")

    metadata = command.dialogue_metadata
    plot_rules = load_adv1_plot_progression_rules()
    plot = world_state.plots.get(plot_rules.plot_id)
    location = world_state.locations.get(world_state.player.location_id or "")
    location_name = location.name if location is not None else (world_state.player.location_id or "unknown location")
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
    )


class DeterministicDialogueRenderer:
    def render_dialogue(self, render_input: DialogueRenderInput) -> str:
        if render_input.npc_id == "npc_1":
            return self._render_jonas_dialogue(render_input)
        return self._render_default_dialogue(render_input)

    def _render_jonas_dialogue(self, render_input: DialogueRenderInput) -> str:
        if render_input.check_kind == "dialogue_social":
            if render_input.check_is_success:
                return self._render_jonas_social_success(render_input)
            return self._render_jonas_social_failure(render_input)

        if render_input.dialogue_domain == "travel_proposal":
            return self._render_jonas_logistics_reply(render_input)

        if render_input.dialogue_domain == "off_topic_request":
            normalized_text = f"{render_input.utterance_text} {render_input.speech_text}".lower().replace("-", " ")
            if _is_taxi_fare_support_request(normalized_text):
                return (
                    "Jonas Reed gives you a flat, unreadable look, like the request never came close to landing. "
                    "'I am not financing the ride. If the dock matters, find your own way there.'"
                )
            return (
                "Jonas Reed keeps a careful distance, his expression flat. "
                "'Not that. Ask someone else.'"
            )

        if render_input.dialogue_domain == "provocative_or_inappropriate":
            return (
                "Jonas Reed's expression hardens at once, and whatever patience he had turns cold. "
                "'No. Keep this professional.'"
            )

        if render_input.dialogue_domain == "unknown_misc":
            if render_input.lead_flag_active:
                return (
                    "Jonas Reed keeps his answer clipped, like he is already deciding how long this talk should last. "
                    "'Stay on point. We are talking about the dock, or we are done.'"
                )
            return (
                "Jonas Reed gives you nothing beyond a narrow, wary look. "
                "'Stay on point.'"
            )

        if render_input.dialogue_domain == "lead_pressure" or render_input.adjudication_resolution_kind == "guarded":
            if render_input.topic_status == "refused":
                return (
                    "Jonas Reed closes himself off and lets the silence do the work for him. "
                    "He stays guarded and keeps the conversation tight."
                )
            return (
                "Jonas Reed stays guarded and keeps the conversation tight, offering no opening to press further."
            )

        if render_input.dialogue_domain == "lead_topic":
            return self._render_jonas_lead_topic(render_input)

        return self._render_default_dialogue(render_input)

    def _render_jonas_lead_topic(self, render_input: DialogueRenderInput) -> str:
        if render_input.plot_stage == "lead_confirmed" or render_input.lead_flag_active:
            return (
                "Jonas Reed loosens his shoulders just enough to make the shift visible. "
                "When he finally speaks plainly, he points the whole line of inquiry back toward the waterline: "
                "the dock is where the paper trail began."
            )

        if render_input.dialogue_act == "greet":
            return (
                "Jonas Reed gives a brief nod, keeping the exchange short and careful. "
                "Even so, he steers you toward the same answer: the dock is the only place worth checking tonight."
            )

        if render_input.dialogue_act == "ask" and render_input.speech_text:
            return (
                f"Jonas Reed hears '{render_input.speech_text}' and answers without giving much away. "
                "For tonight, he says, the dock is the only place worth checking."
            )

        return (
            "Jonas Reed keeps his voice low and says only what he is willing to stand behind. "
            "The dock is the only place worth checking tonight."
        )

    def _render_jonas_social_success(self, render_input: DialogueRenderInput) -> str:
        if "dialogue_plot_progressed" in set(render_input.applied_effects):
            return (
                "The pressure lands this time. Jonas Reed studies you for a long beat, then relents and points toward the waterline. "
                "He admits the broker used the dock to move papers, and the lead finally takes solid shape."
            )

        return (
            "Jonas Reed gives ground by degrees rather than all at once. "
            "He keeps talking, and the conversation stays productive without opening into anything wilder than the facts already on the table."
        )

    def _render_jonas_social_failure(self, render_input: DialogueRenderInput) -> str:
        return (
            "Whatever leverage you were trying to build, it slips away before Jonas Reed accepts it. "
            "He shuts back down, stays guarded, and gives nothing that would move the lead forward tonight."
        )

    def _render_jonas_logistics_reply(self, render_input: DialogueRenderInput) -> str:
        normalized_text = f"{render_input.utterance_text} {render_input.speech_text}".lower().replace("-", " ")
        if any(phrase in normalized_text for phrase in ("stay in the car", "wait in the car", "wait nearby", "stay nearby", "stay close", "wait close")):
            return (
                "Jonas Reed glances toward the street, measuring exits before he answers. "
                "'I can stay nearby and watch the approach, but I am not planting myself where everyone can read the arrangement.'"
            )
        if any(phrase in normalized_text for phrase in ("back me up", "backup", "back up", "watch my back", "cover me", "come along as backup", "come along as back up")):
            return (
                "Jonas Reed weighs the request for a moment, then answers in the same careful tone he uses for every risky promise. "
                "'Not shoulder to shoulder. I can keep an eye on things from nearby, but if I stand beside you, people start asking why.'"
            )
        if any(
            phrase in normalized_text
            for phrase in ("drive", "spare car", "have a car", "got a car", "ride", "lift", "drop me off", "vehicle")
        ):
            return (
                "Jonas Reed gives the street another glance before he answers, like he is already ruling out half the idea. "
                "'I can get around just fine, but I am not turning this into a personal ride. If you go to the dock, you get yourself there.'"
            )
        return (
            "Jonas Reed glances past you toward the street before he answers. "
            "'If the dock matters, you go. Me showing my face there only makes noise.'"
        )

    def _render_default_dialogue(self, render_input: DialogueRenderInput) -> str:
        return (
            f"{render_input.npc_name} answers in a measured, guarded way that stays within what the moment supports."
        )


def _is_taxi_fare_support_request(normalized_text: str) -> bool:
    if not normalized_text:
        return False
    return any(
        phrase in normalized_text
        for phrase in (
            "spare change",
            "taxi fare",
            "cab fare",
            "money to pay",
            "money for the taxi",
            "money for the ride",
            "money for the trip",
            "pay for the taxi",
            "pay for the ride",
            "pay for the trip",
            "pay the taxi",
            "pay the fare",
            "cash for the ride",
            "cash for the trip",
            "cover the fare",
        )
    )
