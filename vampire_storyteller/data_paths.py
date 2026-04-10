from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ADVENTURES_DIR = PROJECT_ROOT / "adventures"
ADVENTURE_ID = "ADV1"
ADVENTURE_ROOT = ADVENTURES_DIR / ADVENTURE_ID
ADVENTURE_CONFIG_DIR = ADVENTURE_ROOT / "config"
ADVENTURE_WORLD_DIR = ADVENTURE_ROOT / "world"
ADVENTURE_PLOTS_DIR = ADVENTURE_ROOT / "plots"
ADVENTURE_NPCS_DIR = ADVENTURE_ROOT / "npcs"
ADVENTURE_LOCATIONS_DIR = ADVENTURE_ROOT / "locations"
ADVENTURE_SAVES_DIR = ADVENTURE_ROOT / "saves"
ADVENTURE_NOTES_DIR = ADVENTURE_ROOT / "notes"
DEFAULT_SAVE_PATH = ADVENTURE_SAVES_DIR / "current_save.json"


def get_default_save_path() -> Path:
    return DEFAULT_SAVE_PATH


def get_adventure_root(adventure_id: str = ADVENTURE_ID) -> Path:
    return ADVENTURES_DIR / adventure_id


def get_adventure_metadata_path(adventure_id: str = ADVENTURE_ID) -> Path:
    return get_adventure_root(adventure_id) / "config" / "adventure.json"


def get_adventure_notes_path(adventure_id: str = ADVENTURE_ID) -> Path:
    return get_adventure_root(adventure_id) / "notes" / "README.md"


def get_adventure_config_path(adventure_id: str = ADVENTURE_ID) -> Path:
    return get_adventure_metadata_path(adventure_id)


def get_adventure_world_path(adventure_id: str = ADVENTURE_ID) -> Path:
    return get_adventure_root(adventure_id) / "world"


def get_adventure_player_seed_path(adventure_id: str = ADVENTURE_ID) -> Path:
    return get_adventure_world_path(adventure_id) / "player.json"


def get_adventure_time_seed_path(adventure_id: str = ADVENTURE_ID) -> Path:
    return get_adventure_world_path(adventure_id) / "time.json"


def get_adventure_locations_seed_path(adventure_id: str = ADVENTURE_ID) -> Path:
    return get_adventure_root(adventure_id) / "locations" / "locations.json"


def get_adventure_npcs_seed_path(adventure_id: str = ADVENTURE_ID) -> Path:
    return get_adventure_root(adventure_id) / "npcs" / "npcs.json"


def get_adventure_plots_seed_path(adventure_id: str = ADVENTURE_ID) -> Path:
    return get_adventure_plot_threads_seed_path(adventure_id)


def get_adventure_plot_threads_seed_path(adventure_id: str = ADVENTURE_ID) -> Path:
    return get_adventure_root(adventure_id) / "plots" / "plot_threads.json"


def get_adventure_plot_progression_path(adventure_id: str = ADVENTURE_ID) -> Path:
    return get_adventure_root(adventure_id) / "plots" / "plot_progression.json"


def get_adventure_plot_resolution_path(adventure_id: str = ADVENTURE_ID) -> Path:
    return get_adventure_root(adventure_id) / "plots" / "plot_resolution.json"


def ensure_adventure_directories() -> None:
    for directory in (
        ADVENTURE_CONFIG_DIR,
        ADVENTURE_WORLD_DIR,
        ADVENTURE_PLOTS_DIR,
        ADVENTURE_NPCS_DIR,
        ADVENTURE_LOCATIONS_DIR,
        ADVENTURE_SAVES_DIR,
        ADVENTURE_NOTES_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)


def ensure_data_directories() -> None:
    ensure_adventure_directories()
