from __future__ import annotations

from typing import Any

from .context_builder import (
    build_scene_snapshot,
    narration_payload_to_prompt_json,
    snapshot_to_footer_text,
    snapshot_to_narration_payload,
)
from .scene_models import SceneSnapshot
from .world_state import WorldState


class OpenAISceneNarrativeProvider:
    def __init__(self, api_key: str, model: str, client: Any | None = None) -> None:
        self._model = model
        self._client = client if client is not None else self._create_client(api_key)

    def render_scene(self, world_state: WorldState) -> str:
        snapshot = build_scene_snapshot(world_state)
        prompt = self._build_prompt(narration_payload_to_prompt_json(snapshot_to_narration_payload(snapshot)))
        response = self._client.responses.create(model=self._model, input=prompt)
        output_text = getattr(response, "output_text", "")
        if not isinstance(output_text, str) or not output_text.strip():
            raise RuntimeError("OpenAI scene response did not contain text")
        prose_text = output_text.strip()
        return self._combine_prose_and_footer(prose_text, snapshot)

    def _create_client(self, api_key: str) -> Any:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai package is required for OpenAISceneNarrativeProvider") from exc

        return OpenAI(api_key=api_key)

    def _build_prompt(self, snapshot_json: str) -> str:
        return "\n".join(
            [
                "You are narrating a Vampire: The Masquerade scene from deterministic state.",
                "Use only the supplied JSON snapshot as source of truth.",
                "Write 1 to 3 short paragraphs of plain text only.",
                "Be atmospheric but restrained.",
                "Do not invent weather, sounds, architecture, room details, crowd details, lighting, smells, motion, or emotional beats unless explicitly present in the snapshot.",
                "Do not invent new exits, entities, plot stages, or recent events.",
                "Do not contradict NPC presence or absence.",
                "If information is absent, omit it.",
                "Prefer concise grounded prose over embellished prose.",
                "Do not add bullet points, markdown, or a verification footer.",
                "",
                "Authoritative scene snapshot JSON:",
                snapshot_json,
            ]
        )

    def _combine_prose_and_footer(self, prose_text: str, snapshot: SceneSnapshot) -> str:
        footer_text = snapshot_to_footer_text(snapshot)
        if not prose_text:
            return footer_text
        return f"{prose_text}\n\n---\n{footer_text}"
