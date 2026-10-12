"""Feature extraction and JSONL export for the non-LLM ranking model."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .evaluation import ExerciseSpec, evaluate_source
from .snapshots import SnapshotTransition, TimelineAnalysis


@dataclass(frozen=True)
class TransitionFeatures:
    from_snapshot: int
    to_snapshot: int
    event: str
    matched_functions: int
    score: int
    loop_depth_change: int
    loop_count_change: int
    cyclomatic_complexity_change: int
    repeated_sort_change: int
    list_membership_change: int
    string_concat_change: int
    correctness_change: float | None
    runtime_change_percent: float | None
    baseline_label: str
    analysis_error: str | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def extract_transition_features(
    transition: SnapshotTransition, spec: ExerciseSpec | None = None,
) -> TransitionFeatures:
    """Convert one edit into model-ready numeric features.

    Negative structural values mean that the after-version has less of that
    pattern. `baseline_label` is weak supervision only; human labels replace it
    when creating the final training set.
    """
    changes = transition.changes
    before_eval = after_eval = None
    if spec and not transition.analysis_error:
        before_eval = evaluate_source(transition.before.source, spec)
        after_eval = evaluate_source(transition.after.source, spec)
    runtime_change = None
    if before_eval and after_eval and before_eval.median_runtime_ms and after_eval.median_runtime_ms:
        runtime_change = round((after_eval.median_runtime_ms - before_eval.median_runtime_ms)
                               / before_eval.median_runtime_ms * 100, 3)
    return TransitionFeatures(
        from_snapshot=transition.before.sequence,
        to_snapshot=transition.after.sequence,
        event=transition.after.event,
        matched_functions=len(changes), score=transition.score,
        loop_depth_change=sum(item.after.max_loop_depth - item.before.max_loop_depth for item in changes),
        loop_count_change=sum(item.after.loop_count - item.before.loop_count for item in changes),
        cyclomatic_complexity_change=sum(item.after.cyclomatic_complexity - item.before.cyclomatic_complexity for item in changes),
        repeated_sort_change=sum(item.after.repeated_sort_calls - item.before.repeated_sort_calls for item in changes),
        list_membership_change=sum(item.after.list_membership_checks - item.before.list_membership_checks for item in changes),
        string_concat_change=sum(item.after.string_concat_in_loop - item.before.string_concat_in_loop for item in changes),
        correctness_change=(round(after_eval.pass_rate - before_eval.pass_rate, 3)
                            if before_eval and after_eval else None),
        runtime_change_percent=runtime_change,
        baseline_label=("meaningful_improvement" if transition.is_meaningful else "not_meaningful"),
        analysis_error=transition.analysis_error,
    )


def export_timeline_jsonl(report: TimelineAnalysis, destination: Path,
                          spec: ExerciseSpec | None = None) -> list[TransitionFeatures]:
    """Write one labelled candidate transition per JSONL line."""
    features = [extract_transition_features(item, spec) for item in report.transitions]
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("".join(json.dumps(item.to_dict()) + "\n" for item in features), encoding="utf-8")
    return features
