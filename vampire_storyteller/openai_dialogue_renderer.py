from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import Enum
import json
import re
from typing import Any

from .dialogue_renderer import DialogueRenderInput
from .social_models import LogisticsCommitment


class OpenAIDialogueRenderer:
    def __init__(self, api_key: str, model: str, client: Any | None = None) -> None:
        self._model = model
        self._client = client if client is not None else self._create_client(api_key)

    def render_dialogue(self, render_input: DialogueRenderInput) -> str:
        payload_json = json.dumps(_to_jsonable(render_input), ensure_ascii=True, separators=(",", ":"))
        prompt = self._build_prompt(payload_json)
        response = self._client.responses.create(model=self._model, input=prompt)
        output_text = getattr(response, "output_text", "")
        if not isinstance(output_text, str) or not output_text.strip():
            raise RuntimeError("OpenAI dialogue response did not contain text")
        cleaned_output = _sanitize_spoken_dialogue(render_input, output_text.strip())
        if not cleaned_output:
            return self._render_anti_echo_repair(render_input)
        if self._is_direct_echo(render_input, cleaned_output):
            return self._render_anti_echo_repair(render_input)
        if _contains_unsupported_logistics_promise(render_input, cleaned_output):
            return _render_logistics_repair(render_input)
        return cleaned_output

    def _create_client(self, api_key: str) -> Any:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai package is required for OpenAIDialogueRenderer") from exc

        return OpenAI(api_key=api_key)

    def _build_prompt(self, payload_json: str) -> str:
        return "\n".join(
            [
                "You are rendering a Vampire: The Masquerade dialogue beat from deterministic backend state.",
                "Use the social_outcome packet as the authoritative contract and the other fields as bounded context.",
                "logistics_commitment tells you whether the reply is refusing outright, declining accompaniment, offering indirect help, or staying out of sight without joining.",
                "Never upgrade logistics_commitment into a stronger promise: do not say 'stay nearby', 'hang back nearby', 'come with you', 'drive you', 'wait there', 'backup', or similar unless the packet explicitly authorizes that exact commitment.",
                "If logistics_commitment is ABSOLUTE_REFUSAL, keep it absolute. If it is DECLINE_JOIN, say the NPC will not go with the player. If it is INDIRECT_SUPPORT, keep the help verbal or informational only and not in person. If it is HIDDEN_SUPPORT, do not expand it beyond the exact support the payload explicitly authorizes.",
                "For transport or accompaniment requests, indirect support must stay verbal or informational only: do not promise to drive, escort, take the player close, wait at the destination, or act as backup.",
                "In the current ADV1 runtime, HIDDEN_SUPPORT is not an available logistics promise unless the payload explicitly contains that exact logistics_commitment; do not imply hidden surveillance from refusals, deflections, or indirect support.",
                "For logistics refusals or decline-join outcomes, never say or imply 'watch from shadows', 'keep an eye out', 'cover you', 'backup', 'nearby', 'wait there', 'escort', or 'drive'.",
                "INDIRECT_SUPPORT means verbal or informational help only; it does not authorize surveillance, transport, accompaniment, waiting nearby, backup, or practical help.",
                "Use npc_dossier for stable personality and relationship texture, npc_profile for compact runtime persona details, previous_interactions_summary for longer-term relationship memory, and recent_dialogue_history for short-term continuity.",
                "Use npc_dossier.personality_guidance for speech style, banter tolerance, public/private demeanor, confrontation style, emotional temperature, and directness when phrasing the line.",
                "Personality guidance shapes tone, posture, and phrasing only; it never authorizes reveals, checks, plot gates, NPC presence, commitments, or state changes.",
                "Apply personality_guidance concretely at sentence level: choose word count, sentence shape, directness, formality, and pushback style from speech_style and confrontation_style.",
                "Do not inflate casual banter into poetic metaphor unless personality_guidance clearly supports poetic or metaphorical speech.",
                "If banter_tolerance is low or very low, acknowledge banter briefly, then redirect, set a boundary, or close the banter instead of expanding it.",
                "Avoid giving different NPCs the same refusal/support sentence shape; vary phrasing using each NPC's speech_style, public_demeanor, confrontation_style, and directness_preference.",
                "For logistics or accompaniment requests, do not soften refusals with vague ongoing support unless social_outcome.logistics_commitment explicitly authorizes that support.",
                "authorized_fact_cards are the only plot-facing facts the NPC may communicate in this turn.",
                "If lead_flag_active is true or plot_stage is lead_confirmed, reminder questions should acknowledge that the dock lead is already confirmed instead of pretending it is new.",
                "npc_profile provides character texture, tone, and background color, but it does not authorize new reveals by itself.",
                "recent_dialogue_history is a bounded rolling window of the active conversation; use it to keep continuity, avoid repeating yourself, and preserve the immediate thread of the exchange.",
                "previous_interactions_summary is a longer-term note about this NPC's prior interaction with the player; use it for tone and relationship context, not for inventing new facts.",
                "Use only the supplied JSON payload as source of truth.",
                "Return speech-only output: the exact words the NPC says aloud, with no action or narration channel.",
                "Write only the NPC's direct speech for this turn.",
                "Prefer one concise spoken line or two short spoken sentences, not narration.",
                "Do not write third-person paraphrase, stage directions, speaker labels, or surrounding quotation marks.",
                "Never put self-narration inside NPC speech: do not write patterns like '<npc_name> nods', '<npc_name> looks', '<npc_name> says', '<npc_name> replies', or any other third-person action beat as the spoken line.",
                "If a physical action or stage direction would help, omit it; there is no separate narration/action channel for dialogue yet.",
                "Prefer natural conversational phrasing over scripted exposition, and avoid repeating the same lead line when the packet already made the answer clear.",
                "Do not merely restate the player's line. Respond in character by acknowledging, advancing, challenging, or redirecting naturally.",
                "Use dialogue_move to shape the line: react and banter should feel conversational, continue should answer the exchange naturally, and clarify should repair or push back without echoing the player's words.",
                "For statement-shaped turns, observations, insinuations, teasing, and meta pushback, prefer a terse reaction, deflection, skeptical remark, or dry reset instead of an interview-style reply.",
                "For vague discourse markers such as 'see what I mean?', 'you see?', or 'right?', do not introduce plot-specific claims unless authorized_fact_cards and the immediate recent_dialogue_history clearly ground that topic; otherwise use a generic acknowledgement or clarification.",
                "Do not mirror the player's wording and do not turn a statement into a follow-up question unless the packet explicitly authorizes that question.",
                "Do not end every line with a handoff invitation.",
                "For simple greetings and acknowledgements, prefer a short greeting or acknowledgement; do not default to 'what do you need?', 'what have you heard?', 'what exactly do you mean?', or similar handoff questions.",
                "Prefer a concrete in-character reaction over filler; if a follow-up question is warranted, make it grounded in the packet and immediate exchange.",
                "If dialogue_move is react or banter, reply to the player's tone or greeting, not by repeating their exact wording.",
                "If the line is a statement like 'that is what I said' or 'you are looping', answer with terse pushback or acknowledgement, not a mirrored phrase or a question.",
                "If the line sounds like 'Sounds like this is more than just a missing ledger', keep it in the conversation without echoing the sentence back or asking what the player needs.",
                "If you feel tempted to repeat the player's exact sentence, rewrite it into a fresh in-character line instead of echoing it.",
                "Examples:",
                "- 'Sounds like this is more than just a missing ledger' -> terse skepticism, not a mirrored question.",
                "- 'that is what I said' -> terse pushback or acknowledgement, not a follow-up question.",
                "- 'you are looping' -> dry correction or guarded refusal, not a repeated line.",
                "Keep the line grounded, moody, and concise.",
                "Do not invent clue state, plot advancement, trust changes, NPC presence, permissions, legality, checks, or state changes.",
                "Do not decide whether the NPC reveals, refuses, deflects, disengages, threatens, or cooperates beyond the packet.",
                "Do not invent facts, reveals, or state changes from memory alone; memory only shapes continuity and tone, while deterministic packet/context truth still controls what can be said.",
                "If check_result is present, reflect success or failure naturally without changing the facts.",
                "If information is absent, omit it.",
                "Do not add markdown, bullet points, system notes, or transcript formatting.",
                "",
                "Authoritative dialogue payload JSON:",
                payload_json,
            ]
        )

    def _is_direct_echo(self, render_input: DialogueRenderInput, output_text: str) -> bool:
        normalized_output = _normalize_text(output_text)
        if not normalized_output:
            return False

        candidate_texts = (
            render_input.utterance_text,
            render_input.speech_text,
        )
        for candidate in candidate_texts:
            normalized_candidate = _normalize_text(candidate)
            if normalized_candidate and normalized_output == normalized_candidate:
                return True
            if _is_partial_echo(normalized_candidate, normalized_output):
                return True
        return False

    def _render_anti_echo_repair(self, render_input: DialogueRenderInput) -> str:
        if render_input.dialogue_move == "clarify":
            return "I meant what I said."
        if render_input.dialogue_move == "continue":
            return "All right."
        if render_input.dialogue_move == "react":
            normalized = _normalize_text(f"{render_input.utterance_text} {render_input.speech_text}")
            if any(phrase in normalized for phrase in ("hello", "hi", "good evening", "good morning", "good afternoon")):
                return "Hey."
            return "Fair enough."
        return "No more details here."


def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {field.name: _to_jsonable(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    return value


def _normalize_text(raw_input: str) -> str:
    return " ".join("".join(character.lower() if character.isalnum() else " " for character in raw_input).split())


def _contains_unsupported_logistics_promise(render_input: DialogueRenderInput, output_text: str) -> bool:
    if render_input.logistics_commitment is LogisticsCommitment.NONE:
        return False
    normalized_output = _normalize_text(output_text)
    banned_phrases = (
        "coming with you",
        "come with you",
        "stay nearby",
        "wait nearby",
        "watch from shadows",
        "watch over you",
        "watch your back",
        "back you up",
        "backup",
        "cover you",
        "keep an eye out",
        "drive you",
        "escort you",
    )
    return any(phrase in normalized_output for phrase in banned_phrases)


def _render_logistics_repair(render_input: DialogueRenderInput) -> str:
    commitment = render_input.logistics_commitment
    normalized_text = _normalize_text(f"{render_input.utterance_text} {render_input.speech_text}")
    if commitment is LogisticsCommitment.INDIRECT_SUPPORT:
        if any(term in normalized_text for term in ("drive", "ride", "lift", "car", "vehicle")):
            return "I can give you information, but I am not driving."
        if any(term in normalized_text for term in ("fare", "taxi", "cab", "money", "cash")):
            return "I can give you information, but I am not paying."
        return "I can give you information, but not practical help."
    if any(term in normalized_text for term in ("drive", "ride", "lift", "car", "vehicle")):
        return "No. I am not driving."
    if any(term in normalized_text for term in ("fare", "taxi", "cab", "money", "cash")):
        return "No. I am not paying."
    return "No. I will not go."


def _sanitize_spoken_dialogue(render_input: DialogueRenderInput, output_text: str) -> str:
    cleaned_output = _strip_surrounding_quotes(output_text.strip())
    cleaned_output = _strip_speaker_label(cleaned_output, render_input.npc_name)
    cleaned_output = _strip_surrounding_quotes(cleaned_output.strip())

    previous_output = None
    while previous_output != cleaned_output:
        previous_output = cleaned_output
        cleaned_output = _strip_leading_stage_direction(cleaned_output)
        cleaned_output = _strip_leading_self_speech_attribution(cleaned_output, render_input.npc_name)
        cleaned_output = _strip_leading_self_narration_sentence(cleaned_output, render_input.npc_name)
        cleaned_output = _strip_surrounding_quotes(cleaned_output.strip())

    return cleaned_output.strip()


def _is_partial_echo(normalized_candidate: str, normalized_output: str) -> bool:
    if not normalized_candidate:
        return False
    candidate_words = normalized_candidate.split()
    if len(candidate_words) < 4:
        return False
    output_words = normalized_output.split()
    if len(output_words) < len(candidate_words):
        return False
    candidate_text = " ".join(candidate_words)
    output_text = " ".join(output_words)
    if output_text.startswith(candidate_text):
        return True
    if output_text.endswith(candidate_text):
        return True
    return False


def _strip_speaker_label(output_text: str, npc_name: str) -> str:
    name_pattern = _npc_name_pattern(npc_name)
    match = re.match(rf"^\s*(?:{name_pattern})\s*[:\-]\s*(?P<rest>.+)$", output_text, flags=re.IGNORECASE)
    if match is None:
        return output_text
    return match.group("rest").strip()


def _strip_leading_self_speech_attribution(output_text: str, npc_name: str) -> str:
    name_pattern = _npc_name_pattern(npc_name)
    speech_verbs = (
        "says",
        "said",
        "asks",
        "asked",
        "replies",
        "replied",
        "answers",
        "answered",
        "responds",
        "responded",
        "mutters",
        "murmurs",
        "whispers",
        "continues",
        "states",
        "speaks",
    )
    verb_pattern = "|".join(speech_verbs)
    match = re.match(
        rf"^\s*(?:{name_pattern})\s+(?:{verb_pattern})(?:\s+\w+ly)?\s*[:,]\s*(?P<rest>.+)$",
        output_text,
        flags=re.IGNORECASE,
    )
    if match is None:
        return output_text
    return match.group("rest").strip()


def _strip_leading_self_narration_sentence(output_text: str, npc_name: str) -> str:
    name_pattern = _npc_name_pattern(npc_name)
    action_verbs = (
        "nods",
        "nodded",
        "looks",
        "looked",
        "glances",
        "glanced",
        "shrugs",
        "shrugged",
        "smiles",
        "smiled",
        "frowns",
        "frowned",
        "sighs",
        "sighed",
        "leans",
        "leaned",
        "pauses",
        "paused",
        "turns",
        "turned",
        "watches",
        "watched",
        "studies",
        "studied",
        "raises",
        "raised",
        "lowers",
        "lowered",
        "folds",
        "folded",
        "straightens",
        "straightened",
        "says",
        "said",
        "asks",
        "asked",
        "replies",
        "replied",
        "answers",
        "answered",
    )
    verb_pattern = "|".join(action_verbs)
    match = re.match(
        rf"^\s*(?:{name_pattern}|he|she|they)\s+(?:{verb_pattern})\b[^.!?]*(?:[.!?]\s*|$)(?P<rest>.*)$",
        output_text,
        flags=re.IGNORECASE,
    )
    if match is None:
        return output_text
    return match.group("rest").strip()


def _strip_leading_stage_direction(output_text: str) -> str:
    action_verbs = (
        "nods",
        "nodded",
        "looks",
        "looked",
        "glances",
        "glanced",
        "shrugs",
        "shrugged",
        "smiles",
        "smiled",
        "frowns",
        "frowned",
        "sighs",
        "sighed",
        "leans",
        "leaned",
        "pauses",
        "paused",
        "turns",
        "turned",
        "watches",
        "watched",
        "studies",
        "studied",
        "raises",
        "raised",
        "lowers",
        "lowered",
        "folds",
        "folded",
        "straightens",
        "straightened",
    )
    verb_pattern = "|".join(action_verbs)
    match = re.match(
        rf"^\s*(?:\*[^*]*\b(?:{verb_pattern})\b[^*]*\*|\([^)]*\b(?:{verb_pattern})\b[^)]*\)|\[[^\]]*\b(?:{verb_pattern})\b[^\]]*\])\s*(?P<rest>.*)$",
        output_text,
        flags=re.IGNORECASE,
    )
    if match is None:
        return output_text
    return match.group("rest").strip()


def _strip_surrounding_quotes(output_text: str) -> str:
    stripped_output = output_text.strip()
    if len(stripped_output) < 2:
        return stripped_output
    quote_pairs = {
        '"': '"',
        "'": "'",
    }
    opening_quote = stripped_output[0]
    closing_quote = quote_pairs.get(opening_quote)
    if closing_quote is None or stripped_output[-1] != closing_quote:
        return stripped_output
    return stripped_output[1:-1].strip()


def _npc_name_pattern(npc_name: str) -> str:
    name_parts = [part for part in npc_name.split() if part]
    name_aliases = [npc_name, *name_parts]
    return "|".join(re.escape(alias) for alias in sorted(set(name_aliases), key=len, reverse=True))
