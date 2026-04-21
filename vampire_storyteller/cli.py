from __future__ import annotations

from dataclasses import dataclass

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


class _UnavailableOpenAIDialogueRenderer:
    def __init__(self, reason: str) -> None:
        self._reason = reason

    def render_dialogue(self, render_input) -> str:
        raise RuntimeError(self._reason)


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


def _resolve_runtime_mode(config: AppConfig) -> str:
    if config.runtime_mode is not None:
        return config.runtime_mode
    if config.use_openai_storyteller_mode:
        return "openai_storyteller"
    if config.use_openai_scene_provider or config.use_openai_dialogue_intent_adapter or config.use_openai_dialogue_renderer:
        return "mixed"
    return "deterministic"


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
        reason = (
            "OpenAI dialogue renderer requested but OPENAI_API_KEY is missing; "
            "deterministic dialogue rendering is disabled in OpenAI dialogue mode, so dialogue turns will fail explicitly."
        )
        return _UnavailableOpenAIDialogueRenderer(reason), reason

    try:
        return OpenAIDialogueRenderer(api_key=config.openai_api_key, model=config.openai_model), None
    except Exception as exc:
        reason = (
            "OpenAI dialogue renderer unavailable; deterministic dialogue rendering is disabled in OpenAI dialogue mode, "
            f"so dialogue turns will fail explicitly. ({exc})"
        )
        return _UnavailableOpenAIDialogueRenderer(reason), reason


def build_runtime_composition(config: AppConfig | None = None) -> RuntimeComposition:
    config = load_config() if config is None else config
    runtime_mode = _resolve_runtime_mode(config)
    if runtime_mode == "openai_storyteller":
        return _build_full_openai_storyteller_composition(config)
    if runtime_mode == "deterministic":
        return RuntimeComposition(
            scene_provider=DeterministicSceneNarrativeProvider(),
            dialogue_intent_adapter=NullDialogueIntentAdapter(),
            dialogue_renderer=DeterministicDialogueRenderer(),
            mode_label="Deterministic",
            scene_label="deterministic",
            dialogue_intent_label="deterministic",
            dialogue_render_label="deterministic",
            notices=(),
            full_openai_storyteller_mode=False,
        )

    scene_provider, scene_notice = build_scene_provider(config)
    dialogue_intent_adapter, dialogue_notice = build_dialogue_intent_adapter(config)
    dialogue_renderer, renderer_notice = build_dialogue_renderer(config)
    notices = tuple(notice for notice in (scene_notice, dialogue_notice, renderer_notice) if notice is not None)
    return RuntimeComposition(
        scene_provider=scene_provider,
        dialogue_intent_adapter=dialogue_intent_adapter,
        dialogue_renderer=dialogue_renderer,
        mode_label=_mode_label_for_mixed_runtime(config),
        scene_label=_component_label(scene_provider, "OpenAI", "deterministic"),
        dialogue_intent_label=_component_label(dialogue_intent_adapter, "OpenAI", "deterministic"),
        dialogue_render_label=_dialogue_render_label(config, dialogue_renderer),
        notices=notices,
        full_openai_storyteller_mode=False,
    )


def _build_full_openai_storyteller_composition(config: AppConfig) -> RuntimeComposition:
    if not config.openai_api_key:
        raise RuntimeError("Full OpenAI storyteller mode requires OPENAI_API_KEY.")

    try:
        scene_provider = OpenAISceneNarrativeProvider(api_key=config.openai_api_key, model=config.openai_model)
        dialogue_intent_adapter = OpenAIDialogueIntentAdapter(api_key=config.openai_api_key, model=config.openai_model)
        dialogue_renderer = OpenAIDialogueRenderer(api_key=config.openai_api_key, model=config.openai_model)
    except Exception as exc:
        raise RuntimeError(f"Full OpenAI storyteller mode failed to initialize: {exc}") from exc

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


def _mode_label_for_mixed_runtime(config: AppConfig) -> str:
    if config.runtime_mode == "mixed":
        return "Mixed"
    if config.use_openai_scene_provider or config.use_openai_dialogue_intent_adapter or config.use_openai_dialogue_renderer:
        return "Mixed"
    return "Deterministic"


def _component_label(component: object, openai_label: str, deterministic_label: str) -> str:
    return openai_label if isinstance(component, (OpenAISceneNarrativeProvider, OpenAIDialogueIntentAdapter)) else deterministic_label


def _dialogue_render_label(config: AppConfig, dialogue_renderer: DialogueRenderer) -> str:
    if isinstance(dialogue_renderer, OpenAIDialogueRenderer):
        return "OpenAI"
    if config.use_openai_dialogue_renderer:
        return "OpenAI (unavailable)"
    return "deterministic"


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
        f"Mode: {runtime.mode_label}",
        f"Scene narration: {runtime.scene_label}",
        f"Dialogue intent: {runtime.dialogue_intent_label}",
        f"Dialogue rendering: {runtime.dialogue_render_label}",
        f"Provider: {runtime.scene_provider.__class__.__name__}",
    ]
    if config.use_openai_storyteller_mode or config.use_openai_scene_provider or isinstance(runtime.scene_provider, OpenAISceneNarrativeProvider):
        lines.append(f"Model: {config.openai_model}")
    if config.use_openai_storyteller_mode or config.use_openai_dialogue_intent_adapter or isinstance(runtime.dialogue_intent_adapter, OpenAIDialogueIntentAdapter):
        lines.append(f"Dialogue model: {config.openai_model}")
    if config.use_openai_storyteller_mode or config.use_openai_dialogue_renderer or isinstance(runtime.dialogue_renderer, OpenAIDialogueRenderer):
        lines.append(f"Dialogue render model: {config.openai_model}")
    lines.append(f"Storyteller preset: {'yes' if config.use_openai_storyteller_mode else 'no'}")
    lines.append(f"Mixed mode: {'yes' if runtime.mode_label == 'Mixed' else 'no'}")
    lines.append(f"Fallback: {'yes' if runtime.notices else 'no'}")
    for notice in runtime.notices:
        lines.append(f"Notice: {notice}")
    lines.append(f"Save: {get_default_save_path().as_posix()}")
    return "\n".join(lines)


if __name__ == "__main__":
    run_cli()
