from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any


DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "app_config.json"
DEFAULT_LOCAL_CONFIG_PATH = PROJECT_ROOT / "config" / "app_config.local.json"
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"


@dataclass(frozen=True, slots=True)
class AppConfig:
    openai_api_key: str | None
    openai_model: str
    use_openai_scene_provider: bool
    use_openai_dialogue_intent_adapter: bool
    use_openai_dialogue_renderer: bool
    use_openai_storyteller_mode: bool = False


def load_config(
    config_path: Path | str | None = None,
    local_config_path: Path | str | None = None,
    dotenv_path: Path | str | None = None,
) -> AppConfig:
    runtime_config = _load_runtime_config(_resolve_path(config_path, DEFAULT_CONFIG_PATH))
    local_runtime_config = _load_runtime_config(_resolve_path(local_config_path, DEFAULT_LOCAL_CONFIG_PATH))
    secret_values = _load_dotenv(_resolve_path(dotenv_path, DEFAULT_ENV_PATH))

    merged_runtime_config = {**runtime_config, **local_runtime_config}
    openai_model = _coerce_str(merged_runtime_config.get("openai_model"), DEFAULT_OPENAI_MODEL)
    use_openai_storyteller_mode = _coerce_bool(merged_runtime_config.get("use_openai_storyteller_mode"), False)
    use_openai_scene_provider = _coerce_bool(merged_runtime_config.get("use_openai_scene_provider"), False)
    use_openai_dialogue_intent_adapter = _coerce_bool(merged_runtime_config.get("use_openai_dialogue_intent_adapter"), False)
    use_openai_dialogue_renderer = _coerce_bool(merged_runtime_config.get("use_openai_dialogue_renderer"), False)
    openai_api_key = os.getenv("OPENAI_API_KEY") or secret_values.get("OPENAI_API_KEY") or None
    return AppConfig(
        openai_api_key=openai_api_key,
        openai_model=openai_model,
        use_openai_storyteller_mode=use_openai_storyteller_mode,
        use_openai_scene_provider=use_openai_scene_provider,
        use_openai_dialogue_intent_adapter=use_openai_dialogue_intent_adapter,
        use_openai_dialogue_renderer=use_openai_dialogue_renderer,
    )


def _resolve_path(path: Path | str | None, default_path: Path) -> Path:
    return default_path if path is None else Path(path)


def _load_runtime_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}

    if not isinstance(loaded, dict):
        return {}

    return loaded


def _load_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    try:
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return values

    for raw_line in raw_lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        values[key] = _strip_wrapping_quotes(value.strip())
    return values


def _strip_wrapping_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _coerce_str(value: Any, default: str) -> str:
    if isinstance(value, str):
        normalized = value.strip()
        if normalized:
            return normalized
    return default


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    return default
