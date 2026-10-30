"""Train on one reviewed dataset and evaluate timeline ranking on another tier.

This deliberately accepts an explicit validation cohort path and has no
final-test default, preventing accidental use of the sealed final-test set.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from code_lens.ml import labels_from_rows, load_jsonl, train


def _labelled_best(attempt: Path) -> tuple[int, int] | None:
    labels = [json.loads(line) for line in (attempt / "gold_labels.jsonl").read_text(encoding="utf-8").splitlines()
              if line.strip()]
    positive = [(row["from_snapshot"], row["to_snapshot"]) for row in labels if row["label"] == 1]
    if len(positive) > 1:
        raise ValueError(f"multiple best labels in {attempt}")
    return positive[0] if positive else None


def _selected(rows: list[dict[str, object]], *, model=None) -> tuple[int, int] | None:
    """Rank stored, correctness-verified features without rerunning student code."""
    eligible = [row for row in rows if row.get("is_eligible_improvement") is True]
    if not eligible:
        return None
    if model is None:
        best = max(eligible, key=lambda row: (
            float(row.get("score", 0)), -float(row.get("growth_exponent_change") or 0),
            -float(row.get("runtime_change_percent") or 0), -int(row["to_snapshot"]),
        ))
    else:
        best = max(eligible, key=lambda row: (model.probability(row), -int(row["to_snapshot"])))
    return int(best["from_snapshot"]), int(best["to_snapshot"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate ML and deterministic timeline ranking on validation data.")
    parser.add_argument("training_dataset", type=Path)
    parser.add_argument("validation_cohort", type=Path)
    parser.add_argument("model_output", type=Path)
    parser.add_argument("report_output", type=Path)
    args = parser.parse_args()
    if "final-test" in args.validation_cohort.parts:
        parser.error("final-test is sealed and cannot be used by this evaluator")
    training_rows = load_jsonl(args.training_dataset)
    model = train(training_rows, labels_from_rows(training_rows))
    model.save(args.model_output)
    attempts = sorted(path.parent for path in args.validation_cohort.rglob("gold_labels.jsonl"))
    if not attempts:
        parser.error("validation cohort contains no labelled attempts")
    results = []
    for attempt in attempts:
        expected = _labelled_best(attempt)
        features = load_jsonl(attempt / "transitions.jsonl")
        deterministic = _selected(features)
        ml = _selected(features, model=model)
        results.append({
            "student_id": json.loads((attempt / "metadata.json").read_text(encoding="utf-8"))["student_id"],
            "attempt_id": attempt.name, "expected_best": expected,
            "deterministic_selected": deterministic, "ml_selected": ml,
            "deterministic_correct": deterministic == expected, "ml_correct": ml == expected,
        })
    summary = {
        "dataset_kind": "synthetic_validation_only",
        "attempts": len(results),
        "deterministic_timeline_accuracy": sum(item["deterministic_correct"] for item in results) / len(results),
        "ml_timeline_accuracy": sum(item["ml_correct"] for item in results) / len(results),
        "no_improvement_attempts": sum(item["expected_best"] is None for item in results),
        "details": results,
    }
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Validation attempts: {summary['attempts']}; ML accuracy: {summary['ml_timeline_accuracy']:.1%}; "
          f"deterministic accuracy: {summary['deterministic_timeline_accuracy']:.1%}")
    print(f"Model: {args.model_output}; report: {args.report_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
