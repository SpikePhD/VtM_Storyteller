from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class PlotStageSemantics:
    stage_id: str
    semantic_category: str
    player_summary: str
    prompt_guidance: str
    allowed_specificity: str


def describe_plot_stage_semantics(
    plot_name: str,
    stage_id: str,
    stage_semantics: Mapping[str, PlotStageSemantics] | None = None,
) -> PlotStageSemantics:
    if stage_semantics is not None:
        semantics = stage_semantics.get(stage_id)
        if semantics is not None:
            if semantics.stage_id == stage_id:
                return semantics
            return PlotStageSemantics(
                stage_id=stage_id,
                semantic_category=semantics.semantic_category,
                player_summary=semantics.player_summary,
                prompt_guidance=semantics.prompt_guidance,
                allowed_specificity=semantics.allowed_specificity,
            )

    return _default_plot_stage_semantics(plot_name, stage_id)


def _default_plot_stage_semantics(plot_name: str, stage_id: str) -> PlotStageSemantics:
    normalized_stage = stage_id.strip().lower()
    if normalized_stage == "hook":
        return PlotStageSemantics(
            stage_id=stage_id,
            semantic_category="premise",
            player_summary=f"{plot_name} is an unresolved mystery.",
            prompt_guidance="Premise only. Keep the scene vague and do not invent a concrete next step, source, or location.",
            allowed_specificity="premise only",
        )
    if normalized_stage == "church_visited":
        return PlotStageSemantics(
            stage_id=stage_id,
            semantic_category="rumor",
            player_summary=f"{plot_name}: a church-records angle is in play.",
            prompt_guidance="Rumor or partial clue only. You may color the scene with a church-records angle, but do not claim the lead is confirmed or actionable.",
            allowed_specificity="rumor only",
        )
    if normalized_stage == "lead_confirmed":
        return PlotStageSemantics(
            stage_id=stage_id,
            semantic_category="confirmed_lead",
            player_summary=f"{plot_name}: the actionable lead is confirmed.",
            prompt_guidance="Confirmed lead. Concrete direction is authorized only because backend state already confirmed it.",
            allowed_specificity="confirmed lead",
        )
    if normalized_stage == "resolved":
        return PlotStageSemantics(
            stage_id=stage_id,
            semantic_category="resolution",
            player_summary=f"{plot_name} is resolved.",
            prompt_guidance="Resolution only. Do not imply a new next step.",
            allowed_specificity="resolution",
        )

    return PlotStageSemantics(
        stage_id=stage_id,
        semantic_category="premise",
        player_summary=f"{plot_name} is active.",
        prompt_guidance="Keep the plot active but do not invent specifics that the backend has not confirmed.",
        allowed_specificity="generic active plot",
    )
