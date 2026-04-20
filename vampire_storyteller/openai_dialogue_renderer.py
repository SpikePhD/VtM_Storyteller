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
                "Use only the supplied JSON payload as source of truth.",
                "Write 1 or 2 short paragraphs of plain text only.",
                "Keep the prose grounded, moody, and concise.",
                "Do not invent clue state, plot advancement, trust changes, NPC presence, permissions, legality, checks, or state changes.",
                "Do not decide whether the NPC reveals, refuses, deflects, disengages, threatens, or cooperates beyond the packet.",
                "If check_result is present, reflect success or failure naturally without changing the facts.",
                "If information is absent, omit it.",
                "Do not add markdown, bullet points, or system notes.",
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
