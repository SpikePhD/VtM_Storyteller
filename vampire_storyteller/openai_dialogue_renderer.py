from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import Enum
import json
from typing import Any

from .dialogue_renderer import DialogueRenderInput


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
        return output_text.strip()

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
                "Use npc_dossier for stable personality and relationship texture, npc_profile for compact runtime persona details, previous_interactions_summary for longer-term relationship memory, and recent_dialogue_history for short-term continuity.",
                "authorized_fact_cards are the only plot-facing facts the NPC may communicate in this turn.",
                "npc_profile provides character texture, tone, and background color, but it does not authorize new reveals by itself.",
                "recent_dialogue_history is a bounded rolling window of the active conversation; use it to keep continuity, avoid repeating yourself, and preserve the immediate thread of the exchange.",
                "previous_interactions_summary is a longer-term note about this NPC's prior interaction with the player; use it for tone and relationship context, not for inventing new facts.",
                "Use only the supplied JSON payload as source of truth.",
                "Write only the NPC's direct speech for this turn.",
                "Prefer one concise spoken line or two short spoken sentences, not narration.",
                "Do not write third-person paraphrase, stage directions, speaker labels, or surrounding quotation marks.",
                "Prefer natural conversational phrasing over scripted exposition, and avoid repeating the same lead line when the packet already made the answer clear.",
                "Do not merely restate the player's line. Respond in character by acknowledging, advancing, challenging, or redirecting naturally.",
                "Use dialogue_move to shape the line: react and banter should feel conversational, continue should answer the exchange naturally, and clarify should repair or push back without echoing the player's words.",
                "Do not end every line with a handoff invitation.",
                "Prefer a concrete in-character reaction over filler; if a follow-up question is warranted, make it grounded in the packet and immediate exchange.",
                "If dialogue_move is react or banter, reply to the player's tone or greeting, not by repeating their exact wording.",
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
