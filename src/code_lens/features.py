"""Feature extraction and JSONL export for the non-LLM ranking model."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

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
    sliding_window_change: int
    before_pass_rate: float | None
    after_pass_rate: float | None
    correctness_change: float | None
    after_is_correct: bool | None
    correctness_preserved: bool | None
    is_eligible_improvement: bool
    runtime_change_percent: float | None
    before_growth_exponent: float | None
    after_growth_exponent: float | None
    growth_exponent_change: float | None
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
    correctness_preserved = (after_eval.pass_rate >= before_eval.pass_rate
                             if before_eval and after_eval else None)
    after_is_correct = after_eval.is_correct if after_eval else None
    eligible = bool(
        transition.is_meaningful
        and after_is_correct
        and correctness_preserved
    )
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
        sliding_window_change=sum(item.after.sliding_window_patterns - item.before.sliding_window_patterns for item in changes),
        before_pass_rate=(round(before_eval.pass_rate, 3) if before_eval else None),
        after_pass_rate=(round(after_eval.pass_rate, 3) if after_eval else None),
        correctness_change=(round(after_eval.pass_rate - before_eval.pass_rate, 3)
                            if before_eval and after_eval else None),
        after_is_correct=after_is_correct,
        correctness_preserved=correctness_preserved,
        is_eligible_improvement=eligible,
        runtime_change_percent=runtime_change,
        before_growth_exponent=(round(before_eval.growth_exponent, 3) if before_eval and before_eval.growth_exponent is not None else None),
        after_growth_exponent=(round(after_eval.growth_exponent, 3) if after_eval and after_eval.growth_exponent is not None else None),
        growth_exponent_change=(round(after_eval.growth_exponent - before_eval.growth_exponent, 3)
                                if before_eval and after_eval and before_eval.growth_exponent is not None
                                and after_eval.growth_exponent is not None else None),
        baseline_label=("meaningful_improvement" if eligible else "not_meaningful"),
        analysis_error=transition.analysis_error,
    )


def export_timeline_jsonl(report: TimelineAnalysis, destination: Path,
                          spec: ExerciseSpec | None = None) -> list[TransitionFeatures]:
    """Write one labelled candidate transition per JSONL line."""
    features = [extract_transition_features(item, spec) for item in report.transitions]
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("".join(json.dumps(item.to_dict()) + "\n" for item in features), encoding="utf-8")
    return features


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    try:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid JSONL in {path}: {error.msg}") from error


def assemble_reviewed_dataset(stores: Iterable[Path], destination: Path) -> list[dict[str, object]]:
    """Join generated features to reviewed labels without mutating either source.

    Each store must contain `transitions.jsonl`, `gold_labels.jsonl`, and
    `metadata.json`. The generated destination is the only dataset intended for
    ML training because every feature row has one validated human label.
    """
    assembled: list[dict[str, object]] = []
    seen: set[tuple[str, str, int, int]] = set()
    for store in stores:
        features_path = store / "transitions.jsonl"
        labels_path = store / "gold_labels.jsonl"
        metadata_path = store / "metadata.json"
        if not all(path.exists() for path in (features_path, labels_path, metadata_path)):
            raise ValueError(f"{store} needs transitions.jsonl, gold_labels.jsonl, and metadata.json")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        student_id = str(metadata["student_id"])
        attempt_id = str(metadata["attempt_id"])
        features = _read_jsonl(features_path)
        labels = _read_jsonl(labels_path)
        feature_by_key = _rows_by_transition(features, features_path)
        label_by_key = _rows_by_transition(labels, labels_path)
        if feature_by_key.keys() != label_by_key.keys():
            missing_labels = sorted(feature_by_key.keys() - label_by_key.keys())
            missing_features = sorted(label_by_key.keys() - feature_by_key.keys())
            raise ValueError(f"transition mismatch for {store}: missing labels={missing_labels}, "
                             f"missing features={missing_features}")
        for key in sorted(feature_by_key):
            label_row = label_by_key[key]
            label = label_row.get("label")
            if isinstance(label, bool) or label not in (0, 1):
                raise ValueError(f"invalid human label for {store} transition {key}: {label!r}")
            identity = (student_id, attempt_id, key[0], key[1])
            if identity in seen:
                raise ValueError(f"duplicate reviewed transition: {identity}")
            seen.add(identity)
            row = dict(feature_by_key[key])
            row.update({
                "label": label,
                "review_decision": label_row.get("decision"),
                "review_reason": label_row.get("reason"),
                "reviewer": label_row.get("reviewer"),
                "review_standard": label_row.get("review_standard"),
                "dataset_source": metadata.get("dataset_source"),
                "student_id": student_id,
                "attempt_id": attempt_id,
                "language": metadata.get("language"),
                "problem_number": metadata.get("problem_reference", {}).get("number"),
                "problem_title": metadata.get("problem_reference", {}).get("title"),
            })
            assembled.append(row)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("".join(json.dumps(row) + "\n" for row in assembled), encoding="utf-8")
    return assembled


def _rows_by_transition(rows: list[dict[str, object]], source: Path) -> dict[tuple[int, int], dict[str, object]]:
    indexed: dict[tuple[int, int], dict[str, object]] = {}
    for row in rows:
        try:
            key = int(row["from_snapshot"]), int(row["to_snapshot"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"{source} row lacks valid snapshot identifiers") from error
        if key in indexed:
            raise ValueError(f"duplicate transition {key} in {source}")
        indexed[key] = row
    return indexed


@dataclass(frozen=True)
class StaticRuleAudit:
    reviewed: int
    static_positive: int
    reviewed_positive: int
    true_positive: int
    true_negative: int
    false_positive: int
    false_negative: int
    disagreements: tuple[dict[str, object], ...]


def audit_static_rules(rows: list[dict[str, object]]) -> StaticRuleAudit:
    """Compare structural scores with reviewed labels; score > 0 is a signal."""
    counts = {"true_positive": 0, "true_negative": 0, "false_positive": 0, "false_negative": 0}
    static_positive = reviewed_positive = 0
    disagreements = []
    for row in rows:
        label = row.get("label")
        if isinstance(label, bool) or label not in (0, 1):
            raise ValueError("audit needs reviewed rows with a numeric label of 0 or 1")
        static_signal = float(row.get("score", 0) or 0) > 0
        static_positive += int(static_signal)
        reviewed_positive += int(label == 1)
        if static_signal and label == 1:
            outcome = "true_positive"
        elif static_signal:
            outcome = "false_positive"
        elif label == 1:
            outcome = "false_negative"
        else:
            outcome = "true_negative"
        counts[outcome] += 1
        if outcome in {"false_positive", "false_negative"}:
            disagreements.append({
                "student_id": row.get("student_id"), "attempt_id": row.get("attempt_id"),
                "from_snapshot": row.get("from_snapshot"), "to_snapshot": row.get("to_snapshot"),
                "static_score": row.get("score"), "reviewed_label": label,
                "review_decision": row.get("review_decision"), "outcome": outcome,
            })
    return StaticRuleAudit(len(rows), static_positive, reviewed_positive, **counts,
                           disagreements=tuple(disagreements))
