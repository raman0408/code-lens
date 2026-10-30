"""Timeline-level eligibility and deterministic best-transition ranking."""

from __future__ import annotations

from dataclasses import dataclass

from .evaluation import ExerciseSpec
from .features import TransitionFeatures, extract_transition_features
from .ml import LogisticRegressionModel
from .snapshots import SnapshotTransition, TimelineAnalysis


@dataclass(frozen=True)
class RankedTransition:
    transition: SnapshotTransition
    features: TransitionFeatures
    rank: int
    evidence: tuple[str, ...]
    ml_probability: float | None = None


@dataclass(frozen=True)
class TimelineRanking:
    candidates: tuple[RankedTransition, ...]
    rejected_count: int

    @property
    def best(self) -> RankedTransition | None:
        return self.candidates[0] if self.candidates else None


def rank_timeline(report: TimelineAnalysis, spec: ExerciseSpec) -> TimelineRanking:
    """Rank only transitions that satisfy the best-transition contract.

    This deterministic ranking is the baseline for the later ML ranker.  It
    prioritises stronger structural evidence, then measured growth reduction,
    then observed runtime reduction.  Earlier transitions break exact ties so
    repeated equivalent snapshots produce a stable result.
    """
    eligible: list[tuple[SnapshotTransition, TransitionFeatures]] = []
    for transition in report.transitions:
        features = extract_transition_features(transition, spec)
        if features.is_eligible_improvement:
            eligible.append((transition, features))

    ordered = sorted(eligible, key=_ranking_key, reverse=True)
    candidates = tuple(RankedTransition(transition, features, index + 1, _evidence(features))
                       for index, (transition, features) in enumerate(ordered))
    return TimelineRanking(candidates, len(report.transitions) - len(candidates))


def rank_timeline_with_model(report: TimelineAnalysis, spec: ExerciseSpec,
                             model: LogisticRegressionModel) -> TimelineRanking:
    """Let the ML model select the best transition from valid candidates.

    Correctness and analysed-improvement eligibility remain hard constraints.
    Within that safe candidate set, the learned probability—not a rule score—
    determines the ranking returned to the application.
    """
    eligible = []
    for transition in report.transitions:
        features = extract_transition_features(transition, spec)
        if features.is_eligible_improvement:
            eligible.append((transition, features, model.probability(features.to_dict())))
    ordered = sorted(eligible, key=lambda item: (item[2], -item[0].after.sequence), reverse=True)
    candidates = tuple(RankedTransition(transition, features, index + 1, _evidence(features), probability)
                       for index, (transition, features, probability) in enumerate(ordered))
    return TimelineRanking(candidates, len(report.transitions) - len(candidates))


def _ranking_key(item: tuple[SnapshotTransition, TransitionFeatures]) -> tuple[float, float, float, int]:
    transition, features = item
    growth_reduction = -(features.growth_exponent_change or 0.0)
    runtime_reduction = -(features.runtime_change_percent or 0.0)
    return float(features.score), growth_reduction, runtime_reduction, -transition.after.sequence


def _evidence(features: TransitionFeatures) -> tuple[str, ...]:
    evidence = []
    if features.score >= 3:
        evidence.append(f"structural score {features.score}")
    if features.growth_exponent_change is not None and features.growth_exponent_change <= -0.25:
        evidence.append(f"growth exponent changed by {features.growth_exponent_change:+.3f}")
    if features.runtime_change_percent is not None and features.runtime_change_percent < 0:
        evidence.append(f"runtime changed by {features.runtime_change_percent:+.1f}%")
    return tuple(evidence)
