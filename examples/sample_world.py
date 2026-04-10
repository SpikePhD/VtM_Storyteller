from __future__ import annotations

import tempfile
import sys
from pathlib import Path


if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vampire_storyteller.game_session import GameSession
from vampire_storyteller.serialization import load_world_state, save_world_state


def main() -> None:
    session = GameSession()
    command_inputs = ["look", "move loc_church", "wait 60", "status"]
    for raw_input in command_inputs:
        result = session.process_input(raw_input)
        print(f"--- COMMAND: {raw_input} ---")
        print(result.output_text)
        print()

    with tempfile.TemporaryDirectory() as temp_dir:
        save_path = Path(temp_dir) / "sample_world.json"
        save_world_state(session.get_world_state(), save_path)
        loaded_world = load_world_state(save_path)

        final_location_id = loaded_world.player.location_id
        if final_location_id is None:
            raise RuntimeError("player location was not set after movement")
        final_location = loaded_world.locations[final_location_id]

        print("World state round-trip succeeded.")
        print(f"Player: {loaded_world.player.name}")
        print(f"Final location: {final_location.name}")
        print(f"Current time: {loaded_world.current_time}")
        print(f"Final hunger: {loaded_world.player.hunger}")
        print(f"Event log entries: {len(loaded_world.event_log)}")


if __name__ == "__main__":
    main()
