from __future__ import annotations

from .config import AppConfig, load_config
from .data_paths import ADVENTURE_ID, ADVENTURE_ROOT, get_default_save_path
from .dialogue_renderer import DeterministicDialogueRenderer, DialogueRenderer
from .game_session import GameSession
from .dialogue_intent_adapter import DialogueIntentAdapter, NullDialogueIntentAdapter, OpenAIDialogueIntentAdapter
from .narrative_provider import DeterministicSceneNarrativeProvider
from .exceptions import CommandParseError, WorldStateError
from .narrative_provider import SceneNarrativeProvider
from .openai_dialogue_renderer import OpenAIDialogueRenderer
from .openai_narrative_provider import OpenAISceneNarrativeProvider


def build_scene_provider(config: AppConfig | None = None) -> tuple[SceneNarrativeProvider, str | None]:
    config = load_config() if config is None else config
    if not config.use_openai_scene_provider:
        return DeterministicSceneNarrativeProvider(), None

    if not config.openai_api_key:
        return (
            DeterministicSceneNarrativeProvider(),
            "OpenAI scene provider requested but OPENAI_API_KEY is missing; using deterministic scenes.",
        )

    try:
        return OpenAISceneNarrativeProvider(api_key=config.openai_api_key, model=config.openai_model), None
    except Exception:
        return DeterministicSceneNarrativeProvider(), "OpenAI scene provider unavailable; using deterministic scenes."


def build_dialogue_intent_adapter(config: AppConfig | None = None) -> tuple[DialogueIntentAdapter, str | None]:
    config = load_config() if config is None else config
    if not config.use_openai_dialogue_intent_adapter:
        return NullDialogueIntentAdapter(), None

    if not config.openai_api_key:
        return (
            NullDialogueIntentAdapter(),
            "OpenAI dialogue intent adapter requested but OPENAI_API_KEY is missing; using deterministic dialogue intent.",
        )

    try:
        return OpenAIDialogueIntentAdapter(api_key=config.openai_api_key, model=config.openai_model), None
    except Exception:
        return NullDialogueIntentAdapter(), "OpenAI dialogue intent adapter unavailable; using deterministic dialogue intent."


def build_dialogue_renderer(config: AppConfig | None = None) -> tuple[DialogueRenderer, str | None]:
    config = load_config() if config is None else config
    if not config.use_openai_dialogue_renderer:
        return DeterministicDialogueRenderer(), None

    if not config.openai_api_key:
        return (
            DeterministicDialogueRenderer(),
            "OpenAI dialogue renderer requested but OPENAI_API_KEY is missing; using deterministic dialogue rendering.",
        )

    try:
        return OpenAIDialogueRenderer(api_key=config.openai_api_key, model=config.openai_model), None
    except Exception:
        return DeterministicDialogueRenderer(), "OpenAI dialogue renderer unavailable; using deterministic dialogue rendering."


def run_cli() -> None:
    config = load_config()
    scene_provider, notice = build_scene_provider(config)
    dialogue_intent_adapter, dialogue_notice = build_dialogue_intent_adapter(config)
    dialogue_renderer, renderer_notice = build_dialogue_renderer(config)
    print(_build_runtime_banner(config, scene_provider, dialogue_intent_adapter, dialogue_renderer, notice, dialogue_notice, renderer_notice))
    print()

    session = GameSession(scene_provider=scene_provider, dialogue_intent_adapter=dialogue_intent_adapter, dialogue_renderer=dialogue_renderer)
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
    scene_provider: SceneNarrativeProvider,
    dialogue_intent_adapter: DialogueIntentAdapter,
    dialogue_renderer: DialogueRenderer,
    notice: str | None,
    dialogue_notice: str | None,
    renderer_notice: str | None,
) -> str:
    runtime_mode = "OpenAI" if isinstance(scene_provider, OpenAISceneNarrativeProvider) else "deterministic"
    dialogue_mode = "OpenAI" if isinstance(dialogue_intent_adapter, OpenAIDialogueIntentAdapter) else "deterministic"
    dialogue_render_mode = "OpenAI" if isinstance(dialogue_renderer, OpenAIDialogueRenderer) else "deterministic"
    lines = [
        "Runtime",
        f"Adventure: {ADVENTURE_ID}",
        f"Root: {ADVENTURE_ROOT.as_posix()}",
        f"Mode: {runtime_mode}",
        f"Dialogue intent: {dialogue_mode}",
        f"Dialogue rendering: {dialogue_render_mode}",
        f"Provider: {scene_provider.__class__.__name__}",
    ]
    if config.use_openai_scene_provider or isinstance(scene_provider, OpenAISceneNarrativeProvider):
        lines.append(f"Model: {config.openai_model}")
    if config.use_openai_dialogue_intent_adapter or isinstance(dialogue_intent_adapter, OpenAIDialogueIntentAdapter):
        lines.append(f"Dialogue model: {config.openai_model}")
    if config.use_openai_dialogue_renderer or isinstance(dialogue_renderer, OpenAIDialogueRenderer):
        lines.append(f"Dialogue render model: {config.openai_model}")
    lines.append(f"Fallback: {'yes' if notice is not None else 'no'}")
    if notice is not None:
        lines.append(f"Notice: {notice}")
    lines.append(f"Dialogue fallback: {'yes' if dialogue_notice is not None else 'no'}")
    if dialogue_notice is not None:
        lines.append(f"Dialogue notice: {dialogue_notice}")
    lines.append(f"Dialogue render fallback: {'yes' if renderer_notice is not None else 'no'}")
    if renderer_notice is not None:
        lines.append(f"Dialogue render notice: {renderer_notice}")
    lines.append(f"Save: {get_default_save_path().as_posix()}")
    return "\n".join(lines)


if __name__ == "__main__":
    run_cli()
