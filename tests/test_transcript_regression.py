from __future__ import annotations

import json
from pathlib import Path
import unittest
from unittest.mock import patch

from vampire_storyteller.dialogue_intent_adapter import NullDialogueIntentAdapter
from vampire_storyteller.dialogue_renderer import DeterministicDialogueRenderer
from vampire_storyteller.dice_engine import DeterministicCheckKind, DeterministicCheckResolution
from vampire_storyteller.game_session import GameSession
from vampire_storyteller.narrative_provider import DeterministicSceneNarrativeProvider


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "transcripts"


class TranscriptRegressionTests(unittest.TestCase):
    def test_transcript_fixtures_preserve_packet_truth(self) -> None:
        fixture_paths = sorted(FIXTURE_DIR.glob("*.json"))
        self.assertTrue(fixture_paths)

        for fixture_path in fixture_paths:
            with self.subTest(fixture=fixture_path.name):
                self._run_fixture(fixture_path)

    def _run_fixture(self, fixture_path: Path) -> None:
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        session = GameSession(
            scene_provider=DeterministicSceneNarrativeProvider(),
            dialogue_intent_adapter=NullDialogueIntentAdapter(),
            dialogue_renderer=DeterministicDialogueRenderer(),
        )

        for index, step in enumerate(fixture["steps"]):
            with self.subTest(fixture=fixture["id"], step=index, raw_input=step["input"]):
                check_result = step.get("check_result")
                if check_result is None:
                    result = session.process_input(step["input"])
                else:
                    with patch(
                        "vampire_storyteller.game_session.resolve_deterministic_check",
                        return_value=self._check_resolution_from_fixture(check_result),
                    ):
                        result = session.process_input(step["input"])

                self._assert_step_expectations(session, result, step.get("expect", {}))

    def _check_resolution_from_fixture(self, data: dict) -> DeterministicCheckResolution:
        return DeterministicCheckResolution(
            kind=DeterministicCheckKind(data["kind"]),
            seed=data["seed"],
            roll_pool=data["roll_pool"],
            difficulty=data["difficulty"],
            individual_rolls=list(data["individual_rolls"]),
            successes=data["successes"],
            is_success=data["is_success"],
        )

    def _assert_step_expectations(self, session: GameSession, result, expect: dict) -> None:
        turn = session.get_last_action_resolution()
        if "canonical" in expect:
            self.assertIsNotNone(turn)
            assert turn is not None
            self.assertEqual(turn.canonical_action_text, expect["canonical"])

        if "render_scene" in expect:
            self.assertEqual(result.render_scene, expect["render_scene"])

        for fragment in expect.get("contains", []):
            self.assertIn(fragment.lower(), result.output_text.lower())

        for fragment in expect.get("not_contains", []):
            self.assertNotIn(fragment.lower(), result.output_text.lower())

        world = session.get_world_state()
        if "location_id" in expect:
            self.assertEqual(world.player.location_id, expect["location_id"])
        if "plot_stage" in expect:
            self.assertEqual(world.plots["plot_1"].stage, expect["plot_stage"])
        if "plot_active" in expect:
            self.assertEqual(world.plots["plot_1"].active, expect["plot_active"])
        for story_flag in expect.get("story_flags_contains", []):
            self.assertIn(story_flag, world.story_flags)

        if turn is None:
            return
        if "dialogue_domain" in expect:
            self.assertIsNotNone(turn.dialogue_adjudication)
            assert turn.dialogue_adjudication is not None
            self.assertEqual(turn.dialogue_adjudication.dialogue_domain.value, expect["dialogue_domain"])
        if "outcome_kind" in expect:
            self.assertIsNotNone(turn.social_outcome)
            assert turn.social_outcome is not None
            self.assertEqual(turn.social_outcome.outcome_kind.value, expect["outcome_kind"])
        if "topic_result" in expect:
            self.assertIsNotNone(turn.social_outcome)
            assert turn.social_outcome is not None
            self.assertEqual(turn.social_outcome.topic_result.value, expect["topic_result"])
        if "logistics_commitment_in" in expect:
            self.assertIsNotNone(turn.social_outcome)
            assert turn.social_outcome is not None
            self.assertIn(turn.social_outcome.logistics_commitment.value, expect["logistics_commitment_in"])
        for applied_effect in expect.get("applied_effects_contains", []):
            self.assertIn(applied_effect, turn.consequence_summary.applied_effects)


if __name__ == "__main__":
    unittest.main()
