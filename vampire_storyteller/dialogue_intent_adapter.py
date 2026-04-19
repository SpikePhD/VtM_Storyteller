from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any, Protocol

from .command_models import DialogueAct
from .models import NPC
from .world_state import WorldState


ALLOWED_DIALOGUE_ACTS: tuple[str, ...] = (
    "greet",
    "ask",
    "accuse",
    "persuade",
    "threaten",
    "unknown",
)


@dataclass(frozen=True, slots=True)
class DialogueIntentContextNPC:
    id: str
    name: str


@dataclass(frozen=True, slots=True)
class DialogueIntentContext:
    raw_input: str
    player_location_id: str
    player_location_name: str
    present_npcs: tuple[DialogueIntentContextNPC, ...]
    conversation_focus_npc_id: str | None
    conversation_focus_npc_name: str | None


@dataclass(frozen=True, slots=True)
class DialogueIntentProposal:
    dialogue_act: str
    target_npc_text: str
    topic: str
    tone: str


class DialogueIntentAdapter(Protocol):
    def propose_dialogue_intent(self, context: DialogueIntentContext) -> DialogueIntentProposal | None:
        """Return a validated dialogue-intent proposal or None."""


class NullDialogueIntentAdapter:
    def propose_dialogue_intent(self, context: DialogueIntentContext) -> DialogueIntentProposal | None:
        return None


class OpenAIDialogueIntentAdapter:
    def __init__(self, api_key: str, model: str, client: Any | None = None) -> None:
        self._model = model
        self._client = client if client is not None else self._create_client(api_key)

    def propose_dialogue_intent(self, context: DialogueIntentContext) -> DialogueIntentProposal | None:
        prompt = self._build_prompt(context)
        response = self._client.responses.create(model=self._model, input=prompt)
        output_text = getattr(response, "output_text", "")
        if not isinstance(output_text, str) or not output_text.strip():
            return None
        return self._validate_proposal_text(output_text)

    def _create_client(self, api_key: str) -> Any:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai package is required for OpenAIDialogueIntentAdapter") from exc

        return OpenAI(api_key=api_key)

    def _build_prompt(self, context: DialogueIntentContext) -> str:
        context_json = json.dumps(asdict(context), ensure_ascii=True, separators=(",", ":"))
        return "\n".join(
            [
                "You classify dialogue intent for a deterministic game engine.",
                "Use only the supplied JSON context as source of truth.",
                "Return exactly one JSON object with only these keys: dialogue_act, target_npc_text, topic, tone.",
                "Do not add markdown, comments, or any extra keys.",
                "Allowed dialogue_act values: greet, ask, accuse, persuade, threaten, unknown.",
                "Do not invent NPCs, relationships, clue state, legality, check outcomes, or world mutations.",
                "target_npc_text is the intended addressee only, not the topic or object being discussed.",
                "If the target is unclear, choose unknown and keep target_npc_text empty or grounded in the addressee from the player input or active focus.",
                "Context JSON:",
                context_json,
            ]
        )

    def _validate_proposal_text(self, output_text: str) -> DialogueIntentProposal | None:
        try:
            payload = json.loads(output_text)
        except json.JSONDecodeError:
            return None

        if not isinstance(payload, dict):
            return None

        expected_keys = {"dialogue_act", "target_npc_text", "topic", "tone"}
        if set(payload.keys()) != expected_keys:
            return None

        dialogue_act = payload.get("dialogue_act")
        target_npc_text = payload.get("target_npc_text")
        topic = payload.get("topic")
        tone = payload.get("tone")
        if not all(isinstance(value, str) for value in (dialogue_act, target_npc_text, topic, tone)):
            return None

        normalized_dialogue_act = dialogue_act.strip().lower()
        if normalized_dialogue_act not in ALLOWED_DIALOGUE_ACTS:
            return None

        return DialogueIntentProposal(
            dialogue_act=normalized_dialogue_act,
            target_npc_text=target_npc_text.strip(),
            topic=topic.strip(),
            tone=tone.strip(),
        )


def build_dialogue_intent_context(
    world_state: WorldState,
    raw_input: str,
    conversation_focus_npc_id: str | None = None,
) -> DialogueIntentContext:
    player_location_id = world_state.player.location_id or ""
    location = world_state.locations.get(player_location_id)
    player_location_name = location.name if location is not None else (player_location_id or "unknown location")
    present_npcs = tuple(
        DialogueIntentContextNPC(id=npc.id, name=npc.name)
        for npc in sorted(
            (npc for npc in world_state.npcs.values() if npc.location_id == player_location_id),
            key=lambda npc: (npc.name.lower(), npc.id),
        )
    )
    focus_npc = world_state.npcs.get(conversation_focus_npc_id) if conversation_focus_npc_id is not None else None
    if focus_npc is not None and focus_npc.location_id != player_location_id:
        focus_npc = None

    return DialogueIntentContext(
        raw_input=raw_input.strip(),
        player_location_id=player_location_id,
        player_location_name=player_location_name,
        present_npcs=present_npcs,
        conversation_focus_npc_id=focus_npc.id if focus_npc is not None else None,
        conversation_focus_npc_name=focus_npc.name if focus_npc is not None else None,
    )


def dialogue_act_from_value(value: str) -> DialogueAct:
    return DialogueAct(value)


def is_pronoun_like_target(target_text: str) -> bool:
    return target_text.strip().lower() in {
        "me",
        "us",
        "you",
        "him",
        "her",
        "them",
        "it",
        "this person",
        "that person",
        "the person",
        "the one",
    }


def is_non_specific_target(target_text: str) -> bool:
    normalized_target = target_text.strip().lower()
    if not normalized_target:
        return True
    return normalized_target in {
        "me",
        "us",
        "you",
        "him",
        "her",
        "them",
        "it",
        "someone",
        "somebody",
        "anyone",
        "anybody",
        "whoever",
        "the person",
        "that person",
        "this person",
        "the one",
        "the guy",
        "the girl",
        "the man",
        "the woman",
        "the npc",
    }


def npc_summary_list(npcs: tuple[DialogueIntentContextNPC, ...]) -> str:
    return ", ".join(f"{npc.name} ({npc.id})" for npc in npcs)


def npc_from_world_state(world_state: WorldState, npc_id: str) -> NPC | None:
    return world_state.npcs.get(npc_id)
