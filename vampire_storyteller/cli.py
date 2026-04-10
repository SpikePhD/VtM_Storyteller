from __future__ import annotations

from .config import AppConfig, load_config
from .game_session import GameSession
from .narrative_provider import DeterministicSceneNarrativeProvider
from .exceptions import CommandParseError, WorldStateError
from .narrative_provider import SceneNarrativeProvider
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


def run_cli() -> None:
    scene_provider, notice = build_scene_provider()
    if notice is not None:
        print(notice)
        print()

    session = GameSession(scene_provider=scene_provider)
    print("Vampire: The Masquerade storyteller prototype")
    print("Type help for commands.")
    print()
    print(session.get_startup_text())

    while True:
        try:
            raw_input = input("> ")
            result = session.process_input(raw_input)
            print()
            print(result.output_text)
            if result.should_quit:
                break
        except CommandParseError as exc:
            print(f"Input error: {exc}")
        except WorldStateError as exc:
            print(f"Action failed: {exc}")
        except EOFError:
            break


if __name__ == "__main__":
    run_cli()
