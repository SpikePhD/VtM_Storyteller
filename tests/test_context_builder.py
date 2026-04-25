from __future__ import annotations

import unittest

from vampire_storyteller.context_builder import build_scene_snapshot, snapshot_to_prompt_text
from vampire_storyteller.exceptions import ContextBuildError
from vampire_storyteller.models import EventLogEntry
from vampire_storyteller.plot_stage_semantics import PlotStageSemantics, describe_plot_stage_semantics
from vampire_storyteller.sample_world import build_sample_world


class ContextBuilderTests(unittest.TestCase):
    def test_snapshot_uses_players_current_location(self) -> None:
        world = build_sample_world()
        snapshot = build_scene_snapshot(world)

        self.assertEqual(snapshot.location_id, "loc_cafe")
        self.assertEqual(snapshot.location_name, "Blackthorn Cafe")
        self.assertEqual(snapshot.location_scene_hook, "Muted conversations and posted notices make the cafe a quiet place to ask questions.")
        self.assertEqual(snapshot.location_notable_features, ["corner booths", "notice board", "narrow back room"])
        self.assertEqual(snapshot.location_flavor_tags, ["quiet", "watchful", "public"])
        self.assertEqual(snapshot.npcs_present[0].trust_level, 0)

    def test_only_npcs_at_player_location_are_included(self) -> None:
        world = build_sample_world()
        snapshot = build_scene_snapshot(world)

        self.assertEqual([npc.id for npc in snapshot.npcs_present], ["npc_1"])

    def test_only_active_plots_are_included(self) -> None:
        world = build_sample_world()
        world.plots["plot_2"] = world.plots["plot_1"].__class__(
            id="plot_2",
            name="Dormant Thread",
            stage="paused",
            active=False,
            triggers=["ignored"],
            consequences=["ignored"],
        )

        snapshot = build_scene_snapshot(world)
        self.assertEqual(snapshot.active_plots, ["Missing Ledger [hook]"])
        self.assertEqual([context.stage_id for context in snapshot.active_plot_contexts], ["hook"])
        self.assertEqual(snapshot.active_plot_contexts[0].semantic_category, "premise")
        self.assertIn("unresolved mystery", snapshot.active_plot_contexts[0].player_summary.lower())

    def test_stage_semantics_helper_distinguishes_premise_and_confirmed_lead(self) -> None:
        premise = describe_plot_stage_semantics(
            "Dummy Mystery",
            "hook",
            {
                "hook": PlotStageSemantics(
                    stage_id="hook",
                    semantic_category="premise",
                    player_summary="The Dummy Mystery is still unresolved.",
                    prompt_guidance="Premise only.",
                    allowed_specificity="premise only",
                )
            },
        )
        confirmed = describe_plot_stage_semantics(
            "Dummy Mystery",
            "lead_confirmed",
            {
                "lead_confirmed": PlotStageSemantics(
                    stage_id="lead_confirmed",
                    semantic_category="confirmed_lead",
                    player_summary="North Dockside is now the confirmed route.",
                    prompt_guidance="Confirmed lead.",
                    allowed_specificity="confirmed lead",
                )
            },
        )

        self.assertEqual(premise.semantic_category, "premise")
        self.assertNotIn("north dockside", premise.player_summary.lower())
        self.assertEqual(confirmed.semantic_category, "confirmed_lead")
        self.assertIn("north dockside", confirmed.player_summary.lower())

    def test_recent_events_are_limited_in_chronological_order(self) -> None:
        world = build_sample_world()
        world.append_event(EventLogEntry(timestamp="t1", description="First", involved_entities=[]))
        world.append_event(EventLogEntry(timestamp="t2", description="Second", involved_entities=[]))
        world.append_event(EventLogEntry(timestamp="t3", description="Third", involved_entities=[]))
        world.append_event(EventLogEntry(timestamp="t4", description="Fourth", involved_entities=[]))

        snapshot = build_scene_snapshot(world, recent_event_limit=2)
        self.assertEqual(snapshot.recent_events, ["Third", "Fourth"])

    def test_recent_events_filter_raw_rolls_and_summarize_dialogue_checks(self) -> None:
        world = build_sample_world()
        world.append_event(
            EventLogEntry(
                timestamp="t1",
                description="Rolled dialogue_social check: 3 dice vs difficulty 6: [8, 2, 7] -> 2 successes.",
                involved_entities=[],
            )
        )
        world.append_event(
            EventLogEntry(
                timestamp="t2",
                description="Dialogue check success: Jonas Reed shares the dock lead and the Missing Ledger plot advances from hook to lead_confirmed.",
                involved_entities=[],
            )
        )

        snapshot = build_scene_snapshot(world, recent_event_limit=3)

        self.assertEqual(snapshot.recent_events, ["Jonas Reed shared the dock lead."])

    def test_recent_events_summarize_plot_advancement_without_raw_stage_log(self) -> None:
        world = build_sample_world()
        world.append_event(
            EventLogEntry(
                timestamp="t1",
                description="Plot 'Missing Ledger' advanced from church_visited to lead_confirmed.",
                involved_entities=[],
            )
        )

        snapshot = build_scene_snapshot(world, recent_event_limit=3)

        self.assertEqual(snapshot.recent_events, ["Missing Ledger: the dock lead is confirmed."])
        self.assertNotIn("advanced from", snapshot.recent_events[0])

    def test_prompt_text_is_stable_and_labeled(self) -> None:
        world = build_sample_world()
        snapshot = build_scene_snapshot(world)
        prompt_text = snapshot_to_prompt_text(snapshot)

        self.assertIn("Time: ", prompt_text)
        self.assertIn("Player: ", prompt_text)
        self.assertIn("Location: ", prompt_text)
        self.assertIn("Exits: ", prompt_text)
        self.assertIn("NPCs Present: ", prompt_text)
        self.assertIn("trust: 0", prompt_text)
        self.assertIn("Active Plots: ", prompt_text)
        self.assertIn("The Missing Ledger is still an unresolved mystery.", prompt_text)
        self.assertIn("Recent Events: ", prompt_text)

    def test_building_without_valid_location_raises(self) -> None:
        world = build_sample_world()
        world.player.location_id = None

        with self.assertRaises(ContextBuildError):
            build_scene_snapshot(world)


if __name__ == "__main__":
    unittest.main()
