from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vampire_storyteller.action_resolution import ActionBlockReason, ActionResolutionKind, NormalizationSource, TurnOutcomeKind
from vampire_storyteller.dice_engine import DeterministicCheckKind, DeterministicCheckResolution
from vampire_storyteller.game_session import GameSession


class RulesResolutionMatrixTests(unittest.TestCase):
    def _ready_investigate_session(self) -> GameSession:
        session = GameSession()
        session.process_input("move loc_church")
        session.process_input("wait 60")
        session.process_input("move loc_dock")
        return session

    def test_direct_command_status_exposes_structured_turn_outcome(self) -> None:
        session = GameSession()

        result = session.process_input("status")
        turn = session.get_last_action_resolution()

        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertEqual(result.output_text.splitlines()[0], "Player: Mara Vale")
        self.assertFalse(result.render_scene)
        self.assertEqual(turn.turn_kind, TurnOutcomeKind.NON_STATEFUL_ACTION)
        self.assertEqual(turn.normalization_source, NormalizationSource.DIRECT_COMMAND)
        self.assertEqual(turn.canonical_action_text, "status")
        self.assertEqual(turn.adjudication.resolution_kind, ActionResolutionKind.AUTOMATIC)
        self.assertFalse(turn.world_state_mutated)

    def test_automatic_look_path_stays_structured_and_non_mutating(self) -> None:
        session = GameSession()

        result = session.process_input("look")
        turn = session.get_last_action_resolution()

        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertTrue(result.render_scene)
        self.assertTrue(result.output_text.strip())
        self.assertEqual(turn.turn_kind, TurnOutcomeKind.NON_STATEFUL_ACTION)
        self.assertEqual(turn.normalization_source, NormalizationSource.INTERPRETED)
        self.assertEqual(turn.canonical_action_text, "look")
        self.assertEqual(turn.adjudication.resolution_kind, ActionResolutionKind.AUTOMATIC)
        self.assertFalse(turn.world_state_mutated)

    def test_interpreted_freeform_speech_round_trips_through_turn_contract(self) -> None:
        session = GameSession()

        result = session.process_input("I speak to Jonas.")
        turn = session.get_last_action_resolution()

        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertTrue(result.output_text.strip())
        self.assertIsNotNone(result.dialogue_presentation)
        assert result.dialogue_presentation is not None
        self.assertEqual(result.dialogue_presentation.npc_display_name, "Jonas Reed")
        self.assertEqual(turn.turn_kind, TurnOutcomeKind.STATEFUL_ACTION)
        self.assertEqual(turn.normalization_source, NormalizationSource.INTERPRETED)
        self.assertEqual(turn.canonical_action_text, "talk npc_1")
        self.assertEqual(turn.adjudication.resolution_kind, ActionResolutionKind.AUTOMATIC)
        self.assertTrue(turn.world_state_mutated)
        self.assertEqual(session.get_conversation_focus_npc_id(), "npc_1")
        self.assertEqual(session.get_world_state().npcs["npc_1"].trust_level, 1)

    def test_blocked_investigate_path_preserves_state_and_block_reason(self) -> None:
        session = GameSession()

        result = session.process_input("investigate")
        turn = session.get_last_action_resolution()

        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertIn("Investigate is blocked", result.output_text)
        self.assertEqual(turn.turn_kind, TurnOutcomeKind.BLOCKED)
        self.assertEqual(turn.normalization_source, NormalizationSource.INTERPRETED)
        self.assertEqual(turn.canonical_action_text, "investigate")
        self.assertEqual(turn.adjudication.resolution_kind, ActionResolutionKind.BLOCKED)
        self.assertEqual(turn.block_reason, ActionBlockReason.PREREQUISITE_NOT_MET)
        self.assertFalse(turn.world_state_mutated)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "hook")
        self.assertEqual(len(session.get_world_state().event_log), 0)

    def test_roll_gated_investigate_path_exposes_check_and_consequence_summary(self) -> None:
        session = self._ready_investigate_session()

        with patch("vampire_storyteller.game_session.resolve_deterministic_check") as mock_resolve:
            mock_resolve.return_value = DeterministicCheckResolution(
                kind=DeterministicCheckKind.INVESTIGATION,
                seed="2026-04-09T23:23:00+02:00|investigate|player_1",
                roll_pool=3,
                difficulty=6,
                individual_rolls=[7, 2, 9],
                successes=2,
                is_success=True,
            )
            result = session.process_input("investigate")

        turn = session.get_last_action_resolution()

        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertEqual(turn.turn_kind, TurnOutcomeKind.STATEFUL_ACTION)
        self.assertEqual(turn.normalization_source, NormalizationSource.INTERPRETED)
        self.assertEqual(turn.canonical_action_text, "investigate")
        self.assertEqual(turn.adjudication.resolution_kind, ActionResolutionKind.ROLL_GATED)
        self.assertIsNotNone(turn.check)
        assert turn.check is not None
        self.assertEqual(turn.check.kind, DeterministicCheckKind.INVESTIGATION)
        self.assertTrue(turn.world_state_mutated)
        self.assertIn("Plot 'Missing Ledger' resolved at North Dockside.", result.output_text)
        self.assertIn("investigate_resolution_success", turn.consequence_summary.applied_effects)
        self.assertEqual(session.get_world_state().plots["plot_1"].stage, "resolved")

    def test_save_load_preserves_persistence_sensitive_turn_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir) / "save.json"
            session = GameSession(save_path=save_path)

            session.process_input("talk npc_1")
            session.process_input("save")

            reloaded_session = GameSession(save_path=save_path)
            reloaded_session.process_input("load")

            self.assertEqual(reloaded_session.get_world_state().npcs["npc_1"].trust_level, 1)
            self.assertIn("trust: 1", reloaded_session.get_startup_text())
            self.assertIsNone(reloaded_session.get_conversation_focus_npc_id())
            self.assertEqual(reloaded_session.get_conversation_stance().name, "NEUTRAL")


if __name__ == "__main__":
    unittest.main()
