from __future__ import annotations

from dataclasses import dataclass

from .config import AppConfig, load_config
from .data_paths import ADVENTURE_ID, ADVENTURE_ROOT, get_default_save_path
from .dialogue_renderer import DialogueRenderer
from .game_session import GameSession
from .dialogue_intent_adapter import DialogueIntentAdapter, OpenAIDialogueIntentAdapter
from .exceptions import CommandParseError, WorldStateError
from .narrative_provider import SceneNarrativeProvider
from .openai_dialogue_renderer import OpenAIDialogueRenderer
from .openai_narrative_provider import OpenAISceneNarrativeProvider


@dataclass(frozen=True, slots=True)
class RuntimeComposition:
    scene_provider: SceneNarrativeProvider
    dialogue_intent_adapter: DialogueIntentAdapter
    dialogue_renderer: DialogueRenderer
    mode_label: str
    scene_label: str
    dialogue_intent_label: str
    dialogue_render_label: str
    notices: tuple[str, ...] = ()
    full_openai_storyteller_mode: bool = False


def build_scene_provider(config: AppConfig | None = None) -> tuple[SceneNarrativeProvider, str | None]:
    config = load_config() if config is None else config
    if not config.openai_api_key:
        raise RuntimeError("OpenAI storyteller mode requires OPENAI_API_KEY.")
    return OpenAISceneNarrativeProvider(api_key=config.openai_api_key, model=config.openai_model), None


def build_dialogue_intent_adapter(config: AppConfig | None = None) -> tuple[DialogueIntentAdapter, str | None]:
    config = load_config() if config is None else config
    if not config.openai_api_key:
        raise RuntimeError("OpenAI storyteller mode requires OPENAI_API_KEY.")
    return OpenAIDialogueIntentAdapter(api_key=config.openai_api_key, model=config.openai_model), None


def build_dialogue_renderer(config: AppConfig | None = None) -> tuple[DialogueRenderer, str | None]:
    config = load_config() if config is None else config
    if not config.openai_api_key:
        raise RuntimeError("OpenAI storyteller mode requires OPENAI_API_KEY.")
    return OpenAIDialogueRenderer(api_key=config.openai_api_key, model=config.openai_model), None


def _build_full_openai_storyteller_composition(config: AppConfig) -> RuntimeComposition:
    if not config.openai_api_key:
        raise RuntimeError("OpenAI storyteller mode requires OPENAI_API_KEY.")

    try:
        scene_provider, _ = build_scene_provider(config)
        dialogue_intent_adapter, _ = build_dialogue_intent_adapter(config)
        dialogue_renderer, _ = build_dialogue_renderer(config)
    except Exception as exc:
        raise RuntimeError(f"OpenAI storyteller mode failed to initialize: {exc}") from exc

    return RuntimeComposition(
        scene_provider=scene_provider,
        dialogue_intent_adapter=dialogue_intent_adapter,
        dialogue_renderer=dialogue_renderer,
        mode_label="OpenAI storyteller",
        scene_label="OpenAI",
        dialogue_intent_label="OpenAI",
        dialogue_render_label="OpenAI",
        notices=(),
        full_openai_storyteller_mode=True,
    )


def build_runtime_composition(config: AppConfig | None = None) -> RuntimeComposition:
    config = load_config() if config is None else config
    return _build_full_openai_storyteller_composition(config)


def run_cli() -> None:
    config = load_config()
    runtime = build_runtime_composition(config)
    print(_build_runtime_banner(config, runtime))
    print()

    session = GameSession(
        scene_provider=runtime.scene_provider,
        dialogue_intent_adapter=runtime.dialogue_intent_adapter,
        dialogue_renderer=runtime.dialogue_renderer,
    )
    print("Vampire: The Masquerade storyteller prototype")
    print("Type help for commands.")
    print()
    print(session.get_startup_text())

    while True:
        try:
            raw_input = input(_build_cli_prompt(session))
            result = session.process_input(raw_input)
            print()
            print(_format_cli_result(result))
            if result.should_quit:
                break
        except CommandParseError as exc:
            print(f"Input error: {exc}")
        except WorldStateError as exc:
            print(f"Action failed: {exc}")
        except EOFError:
            break


def _build_cli_prompt(session: GameSession) -> str:
    focus_npc_id = session.get_conversation_focus_npc_id()
    if focus_npc_id is None:
        return "> "
    npc = session.get_world_state().npcs.get(focus_npc_id)
    if npc is None:
        return "> "
    prompt_name = npc.name.split()[0] if npc.name.strip() else "Talk"
    return f"{prompt_name} > "


def _format_cli_result(result) -> str:
    presentation = result.dialogue_presentation
    if presentation is None:
        return result.output_text

    lines: list[str] = []
    if presentation.focus_changed:
        lines.append(f"Conversation: {presentation.npc_display_name}")
    lines.append(f'Player: "{presentation.player_utterance}"')
    lines.append(f'{presentation.npc_display_name}: "{result.output_text}"')
    return "\n".join(lines)


def _build_runtime_banner(
    config: AppConfig,
    runtime: RuntimeComposition,
) -> str:
    lines = [
        "Runtime",
        f"Adventure: {ADVENTURE_ID}",
        f"Root: {ADVENTURE_ROOT.as_posix()}",
        "Mode: OpenAI storyteller",
        "Scene narration: OpenAI",
        "Dialogue intent: OpenAI",
        "Dialogue rendering: OpenAI",
        f"Provider: {runtime.scene_provider.__class__.__name__}",
        f"Model: {config.openai_model}",
        f"Dialogue model: {config.openai_model}",
        f"Dialogue render model: {config.openai_model}",
        "Preset: openai_storyteller only",
    ]
    lines.append(f"Save: {get_default_save_path().as_posix()}")
    return "\n".join(lines)


if __name__ == "__main__":
    run_cli()
