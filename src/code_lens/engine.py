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
    ml_probability: float | None
    evidence: tuple[str, ...]
    conclusion: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def analyze_attempt(store_directory: Path, spec: ExerciseSpec,
                    model: LogisticRegressionModel | None = None) -> AttemptAnalysis:
    """Analyse a completed snapshot timeline using the project's decision contract.

    With a model, ML ranks all eligible candidates and is the selection
    authority. Without one, the deterministic ranking remains available for
    development and diagnostics.
    """
    report = analyze_snapshots(SnapshotStore(store_directory).load())
    ranking: TimelineRanking = (rank_timeline_with_model(report, spec, model)
                                if model else rank_timeline(report, spec))
    selected = ranking.best
    if selected is None:
        return AttemptAnalysis(
            len(report.snapshots), len(report.transitions), ranking.rejected_count, None,
            "ml" if model else "deterministic", None, (),
            "No qualifying improvement: no transition was fully correct, non-regressive, and supported by analysed improvement evidence.",
        )
    before, after = selected.transition.before.sequence, selected.transition.after.sequence
    probability = selected.ml_probability
    return AttemptAnalysis(
        len(report.snapshots), len(report.transitions), ranking.rejected_count, (before, after),
        "ml" if model else "deterministic", probability, selected.evidence,
        f"Best improvement is version {before} to {after}; version {after} passed all defined tests and was eligible for ranking.",
    )
