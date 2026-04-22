from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
from typing import Any, Protocol

from .adventure_loader import Adv1DialogueDossierDefinition, AdventureContentError, load_adv1_dialogue_dossiers
from .command_models import DialogueAct
from .conversation_context import DialogueHistoryEntry, DialogueMemoryContext
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

ALLOWED_DIALOGUE_MOVES: tuple[str, ...] = (
    "none",
    "react",
    "continue",
    "clarify",
    "banter",
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
    npc_dossier: Adv1DialogueDossierDefinition | None
    conversation_memory: DialogueMemoryContext


@dataclass(frozen=True, slots=True)
class DialogueIntentProposal:
    dialogue_act: str
    target_npc_text: str
    topic: str
    tone: str
    dialogue_move: str = "none"


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
        return self._validate_proposal_text(output_text, context)

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
                "You classify dialogue intent for the OpenAI storyteller backend.",
                "Use only the supplied JSON context as source of truth.",
                "Return exactly one JSON object with only these keys: dialogue_act, dialogue_move, target_npc_text, topic, tone.",
                "Do not add markdown, comments, or any extra keys.",
                "Allowed dialogue_act values: greet, ask, accuse, persuade, threaten, unknown.",
                "Allowed dialogue_move values: none, react, continue, clarify, banter.",
                "The JSON must be directly parseable and must not be wrapped in prose or markdown fences.",
                "Use conversation_memory.recent_dialogue_history for immediate continuity and conversation_memory.previous_interactions_summary for longer-term tone and relationship context.",
                "Do not invent facts, state changes, or reveals from memory; memory only helps classify intent within the supplied context.",
                "Use dialogue_move for statement-shaped or conversational turns: react for acknowledgments and greetings, continue for invitations to keep talking or requests for help/info, clarify for repairs or pushback, and banter for light social back-and-forth.",
                "If the player line is clearly still part of the conversation, return a usable dialogue proposal instead of none.",
                "For declarative, relational, urgency, or pressure lines, keep the turn in dialogue and prefer continue, clarify, or react as appropriate.",
                "Examples:",
                "- 'Quite busy... with a job I want no part of' -> dialogue_act unknown, dialogue_move continue, topic conversation, tone guarded.",
                "- 'But I need your help' -> dialogue_act persuade, dialogue_move continue, topic help, tone urgent.",
                "- 'Listen I don't have time for this. What do you know' -> dialogue_act ask, dialogue_move continue, topic missing_ledger, tone urgent.",
                "- 'A lot, as always. But I am not here to chitty chat. I need info' -> dialogue_act persuade, dialogue_move continue, topic information, tone impatient.",
                "Do not invent NPCs, relationships, clue state, legality, check outcomes, or world mutations.",
                "target_npc_text is the intended addressee only, not the topic or object being discussed.",
                "If the target is unclear, choose the active focus if one exists; otherwise use unknown and keep target_npc_text empty.",
                "Context JSON:",
                context_json,
            ]
        )

    def _validate_proposal_text(self, output_text: str, context: DialogueIntentContext) -> DialogueIntentProposal | None:
        json_text = self._extract_json_text(output_text)
        if json_text is None:
            return None

        try:
            payload = json.loads(json_text)
        except json.JSONDecodeError:
            return None

        if not isinstance(payload, dict):
            return None

        expected_keys = {"dialogue_act", "dialogue_move", "target_npc_text", "topic", "tone"}
        if set(payload.keys()) != expected_keys:
            return None

        dialogue_act = payload.get("dialogue_act")
        dialogue_move = payload.get("dialogue_move")
        target_npc_text = payload.get("target_npc_text")
        topic = payload.get("topic")
        tone = payload.get("tone")
        if not all(isinstance(value, str) for value in (dialogue_act, dialogue_move, target_npc_text, topic, tone)):
            return None

        normalized_dialogue_act = dialogue_act.strip().lower()
        if normalized_dialogue_act not in ALLOWED_DIALOGUE_ACTS:
            return None

        normalized_dialogue_move = self._normalize_dialogue_move(
            dialogue_act=normalized_dialogue_act,
            dialogue_move=dialogue_move.strip().lower(),
            raw_input=context.raw_input,
        )
        normalized_target_npc_text = target_npc_text.strip()
        if not normalized_target_npc_text and context.conversation_focus_npc_name:
            normalized_target_npc_text = context.conversation_focus_npc_name

        return DialogueIntentProposal(
            dialogue_act=normalized_dialogue_act,
            dialogue_move=normalized_dialogue_move,
            target_npc_text=normalized_target_npc_text,
            topic=topic.strip() or "conversation",
            tone=tone.strip() or "curious",
        )

    def _extract_json_text(self, output_text: str) -> str | None:
        stripped_text = output_text.strip()
        fenced_match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped_text, flags=re.DOTALL | re.IGNORECASE)
        if fenced_match is not None:
            stripped_text = fenced_match.group(1).strip()

        if stripped_text.startswith("{") and stripped_text.endswith("}"):
            return stripped_text

        json_match = re.search(r"\{.*\}", stripped_text, flags=re.DOTALL)
        if json_match is None:
            return None
        return json_match.group(0).strip()

    def _normalize_dialogue_move(self, dialogue_act: str, dialogue_move: str, raw_input: str) -> str:
        if dialogue_move not in ALLOWED_DIALOGUE_MOVES:
            dialogue_move = "none"

        normalized_input = self._normalize_text(raw_input)
        if dialogue_act == "greet":
            return "react"

        if dialogue_act in {"ask", "persuade"}:
            if dialogue_move in {"continue", "clarify", "banter"}:
                return dialogue_move
            if self._contains_any(
                normalized_input,
                (
                    "need your help",
                    "need help",
                    "need info",
                    "i need your help",
                    "i need you",
                    "what do you know",
                    "what happened",
                    "tell me",
                    "listen",
                    "i do not have time",
                    "i don't have time",
                    "busy",
                ),
            ):
                return "continue"
            return "continue" if "?" in raw_input else "none"

        if dialogue_act in {"accuse", "threaten"}:
            if dialogue_move in {"clarify", "continue", "banter"}:
                return dialogue_move
            return "clarify" if self._contains_any(normalized_input, ("what do you know", "that sounds wrong", "not true", "i did not", "you just did")) else "none"

        if dialogue_move in {"react", "continue", "clarify", "banter"}:
            return dialogue_move

        if self._contains_any(
            normalized_input,
            (
                "just coming to say hi",
                "coming to say hi",
                "hello there",
                "good evening",
                "good morning",
                "good afternoon",
                "there you are",
                "busy",
                "need your help",
                "need info",
                "what do you know",
                "what happened",
            ),
        ):
            return "continue" if self._contains_any(normalized_input, ("need your help", "need info", "what do you know", "what happened", "busy")) else "react"

        return "none"

    def _normalize_text(self, raw_input: str) -> str:
        return " ".join(re.sub(r"[^a-z0-9]+", " ", raw_input.lower()).split())

    def _contains_any(self, normalized_text: str, phrases: tuple[str, ...]) -> bool:
        return any(self._contains_phrase(normalized_text, phrase) for phrase in phrases)

    def _contains_phrase(self, normalized_text: str, phrase: str) -> bool:
        text_tokens = normalized_text.split()
        phrase_tokens = self._normalize_text(phrase).split()
        if not phrase_tokens:
            return False
        for start in range(0, len(text_tokens) - len(phrase_tokens) + 1):
            if text_tokens[start : start + len(phrase_tokens)] == phrase_tokens:
                return True
        return False


def build_dialogue_intent_context(
    world_state: WorldState,
    raw_input: str,
    conversation_focus_npc_id: str | None = None,
    recent_dialogue_history: tuple[DialogueHistoryEntry, ...] = (),
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
    if focus_npc is None and len(present_npcs) == 1:
        sole_present_npc = world_state.npcs.get(present_npcs[0].id)
        if sole_present_npc is not None and sole_present_npc.location_id == player_location_id:
            focus_npc = sole_present_npc

    previous_interactions_summary = focus_npc.previous_interactions_summary if focus_npc is not None else ""
    conversation_memory = DialogueMemoryContext(
        previous_interactions_summary=previous_interactions_summary,
        recent_dialogue_history=recent_dialogue_history,
    )

    return DialogueIntentContext(
        raw_input=raw_input.strip(),
        player_location_id=player_location_id,
        player_location_name=player_location_name,
        present_npcs=present_npcs,
        conversation_focus_npc_id=focus_npc.id if focus_npc is not None else None,
        conversation_focus_npc_name=focus_npc.name if focus_npc is not None else None,
        npc_dossier=_load_dialogue_dossier(focus_npc.id) if focus_npc is not None else None,
        conversation_memory=conversation_memory,
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


def _load_dialogue_dossier(npc_id: str) -> Adv1DialogueDossierDefinition | None:
    try:
        dossier_state = load_adv1_dialogue_dossiers()
    except AdventureContentError:
        return None
    return dossier_state.npc_definitions.get(npc_id)
