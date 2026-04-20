from __future__ import annotations

from dataclasses import asdict
import json
from typing import Any

from .dialogue_renderer import DialogueRenderInput


class OpenAIDialogueRenderer:
    def __init__(self, api_key: str, model: str, client: Any | None = None) -> None:
        self._model = model
        self._client = client if client is not None else self._create_client(api_key)

    def render_dialogue(self, render_input: DialogueRenderInput) -> str:
        payload_json = json.dumps(asdict(render_input), ensure_ascii=True, separators=(",", ":"))
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
                "Use only the supplied JSON payload as source of truth.",
                "Write 1 or 2 short paragraphs of plain text only.",
                "Keep the prose grounded, moody, and concise.",
                "Do not invent clue state, plot advancement, trust changes, NPC presence, permissions, legality, or check outcomes.",
                "Do not change whether the exchange was productive, guarded, refused, logistical, off-topic, provocative, or misc.",
                "If information is absent, omit it.",
                "Do not add markdown, bullet points, or system notes.",
                "",
                "Authoritative dialogue payload JSON:",
                payload_json,
            ]
        )
