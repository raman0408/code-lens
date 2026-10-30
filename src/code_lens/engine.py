"""Application-facing orchestration for a completed student attempt."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from .evaluation import ExerciseSpec
from .ml import LogisticRegressionModel
from .ranking import TimelineRanking, rank_timeline, rank_timeline_with_model
from .snapshots import SnapshotStore, analyze_snapshots


@dataclass(frozen=True)
class AttemptAnalysis:
    """Stable payload for an API or web application final-report screen."""

    snapshot_count: int
    transition_count: int
    rejected_transition_count: int
    selected_transition: tuple[int, int] | None
    selection_authority: str
    improvement_kind: str | None
    ml_probability: float | None
    evidence: tuple[str, ...]
    student_summary: str | None
    conclusion: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def analyze_attempt(store_directory: Path, spec: ExerciseSpec,
                    model: LogisticRegressionModel | None = None,
                    allow_implementation_improvements: bool = False) -> AttemptAnalysis:
    """Analyse a completed snapshot timeline using the project's decision contract.

    With a model, ML ranks all eligible candidates and is the selection
    authority. Without one, the deterministic ranking remains available for
    development and diagnostics.
    """
    report = analyze_snapshots(SnapshotStore(store_directory).load())
    ranking: TimelineRanking = (
        rank_timeline_with_model(report, spec, model, allow_implementation_improvements)
        if model else rank_timeline(report, spec, allow_implementation_improvements)
    )
    selected = ranking.best
    if selected is None:
        return AttemptAnalysis(
            len(report.snapshots), len(report.transitions), ranking.rejected_count, None,
            "ml" if model else "deterministic", None, None, (), None,
            "No qualifying improvement: no transition was fully correct, non-regressive, and supported by analysed improvement evidence.",
        )
    before, after = selected.transition.before.sequence, selected.transition.after.sequence
    probability = selected.ml_probability
    return AttemptAnalysis(
        len(report.snapshots), len(report.transitions), ranking.rejected_count, (before, after),
        "ml" if model else "deterministic", selected.features.improvement_kind, probability, selected.evidence,
        _student_summary(selected.features),
        (f"Best {selected.features.improvement_kind} improvement is version {before} to {after}; "
         f"version {after} passed all defined tests and was eligible for ranking."),
    )


def _student_summary(features: object) -> str:
    """Translate the selected technical signal into student-facing feedback."""
    if features.improvement_kind == "implementation":
        return (f"You kept every test passing while simplifying the same approach: "
                f"the new version uses {abs(features.ast_node_change)} fewer syntax-tree nodes "
                f"without adding loops.")
    if features.sliding_window_change > 0:
        return "You replaced repeated subarray scans with a sliding window, reducing repeated work."
    if features.repeated_sort_change < 0:
        return "You removed sorting from repeated work, so the solution avoids sorting again and again."
    if features.list_membership_change < 0:
        return "You removed repeated list membership checks, reducing repeated linear searches."
    if features.string_concat_change < 0:
        return "You removed repeated string building inside a loop, reducing repeated copying."
    if features.growth_exponent_change is not None and features.growth_exponent_change <= -0.25:
        return "Your benchmark results indicate that the updated solution grows more slowly as input size increases."
    return "You kept every test passing while making a selected improvement to the solution."
