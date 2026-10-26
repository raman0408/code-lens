from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .evaluation import ExerciseSpec
from .features import (assemble_reviewed_dataset, audit_static_rules, export_timeline_jsonl,
                       extract_transition_features)
from .ml import LogisticRegressionModel, labels_from_rows, load_jsonl, train
from .model import FunctionMetrics, analyze_source, analyze_versions
from .snapshots import SnapshotStore, analyze_snapshots


def _metrics(metrics: FunctionMetrics) -> str:
    """Render the exact static measurements used by the rule engine."""
    return (
        f"complexity={metrics.cyclomatic_complexity}, loops={metrics.loop_count}, "
        f"max nesting={metrics.max_loop_depth}, sorts in loops={metrics.repeated_sort_calls}, "
        f"literal-list membership checks={metrics.list_membership_checks}, "
        f"string concatenations in loops={metrics.string_concat_in_loop}, "
        f"sliding-window patterns={metrics.sliding_window_patterns}"
    )


def _print_comparison_explanation(before_source: str, after_source: str, prefix: str = "") -> None:
    """Print an inspectable trace of the deterministic comparison."""
    before = analyze_source(before_source)
    after = analyze_source(after_source)
    shared_names = sorted(before.functions.keys() & after.functions.keys())
    changes = {change.function: change for change in analyze_versions(before_source, after_source)}
    print(f"{prefix}Compared top-level functions: {', '.join(shared_names) or '(none)'}")
    for name in shared_names:
        change = changes.get(name)
        print(f"{prefix}{name}")
        print(f"{prefix}  before: {_metrics(before.functions[name])}")
        print(f"{prefix}  after:  {_metrics(after.functions[name])}")
        if change is None:
            print(f"{prefix}  rule result: no monitored metric decreased (score: 0)")
            continue
        print(f"{prefix}  rule result: score {change.score} "
              f"({'meaningful' if change.is_meaningful else 'below meaningful threshold of 3'})")
        for points, reason in change.evidence:
            print(f"{prefix}    +{points}: {reason}")


def _print_prediction_explanation(model: LogisticRegressionModel, row: dict[str, object], prefix: str = "") -> None:
    """Show raw feature values and their weighted contribution to one prediction."""
    print(f"{prefix}ML feature trace (raw value; weighted standardized contribution):")
    for name, mean, scale, weight in zip(model.feature_names, model.means, model.scales, model.weights):
        value = 0.0 if row.get(name) is None else float(row[name])
        contribution = weight * ((value - mean) / scale)
        print(f"{prefix}  {name}: {value:g}; {contribution:+.3f}")
    print(f"{prefix}  bias: {model.bias:+.3f}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Find likely performance improvements between Python files.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    compare = subparsers.add_parser("compare", help="compare before.py to after.py")
    compare.add_argument("before", type=Path)
    compare.add_argument("after", type=Path)
    compare.add_argument("--explain", action="store_true", help="show metrics and rule points behind the result")
    capture = subparsers.add_parser("capture", help="record a source snapshot after a compile or submission")
    capture.add_argument("store", type=Path, help="directory for this student's snapshot timeline")
    capture.add_argument("source", type=Path)
    capture.add_argument("--event", choices=("compile", "submission"), required=True)
    timeline = subparsers.add_parser("timeline", help="analyze every consecutive snapshot in a store")
    timeline.add_argument("store", type=Path)
    timeline.add_argument("--explain", action="store_true", help="show evidence for every snapshot transition")
    dataset = subparsers.add_parser("dataset", help="export ML-ready transition features as JSONL")
    dataset.add_argument("store", type=Path)
    dataset.add_argument("output", type=Path)
    dataset.add_argument("--spec", type=Path, help="exercise tests and benchmark configuration")
    reviewed_dataset = subparsers.add_parser("reviewed-dataset", help="join features with reviewed labels for ML training")
    reviewed_dataset.add_argument("output", type=Path)
    reviewed_dataset.add_argument("stores", type=Path, nargs="+",
                                  help="attempt directories containing transitions, labels, and metadata")
    audit = subparsers.add_parser("audit", help="compare static rule signals with reviewed labels")
    audit.add_argument("dataset", type=Path, help="assembled reviewed JSONL dataset")
    audit.add_argument("--details", action="store_true", help="show every static-rule disagreement")
    audit.add_argument("--output", type=Path, help="optional JSON report destination")
    demo = subparsers.add_parser("demo", help="create and analyze a three-version sample timeline")
    demo.add_argument("store", type=Path)
    train_model = subparsers.add_parser("train", help="train a logistic-regression transition classifier")
    train_model.add_argument("dataset", type=Path, help="JSONL rows with human 'label' values (0 or 1)")
    train_model.add_argument("model", type=Path)
    train_model.add_argument("--use-baseline-labels", action="store_true",
                             help="bootstrap only: train from rule-generated labels")
    predict = subparsers.add_parser("predict", help="score a timeline and identify its best predicted transition")
    predict.add_argument("store", type=Path)
    predict.add_argument("model", type=Path)
    predict.add_argument("--spec", type=Path, help="optional exercise evaluation configuration")
    predict.add_argument("--explain", action="store_true", help="show rule and ML-feature evidence for each prediction")
    args = parser.parse_args()
    if args.command == "capture":
        snapshot = SnapshotStore(args.store).capture(args.source.read_text(encoding="utf-8"), args.event)
        print(f"Captured snapshot {snapshot.sequence} ({snapshot.event}, {snapshot.source_hash[:12]}).")
        return 0
    if args.command == "timeline":
        report = analyze_snapshots(SnapshotStore(args.store).load())
        if args.explain:
            print("Timeline evidence:")
            for transition in report.transitions:
                print(f"Snapshot {transition.before.sequence} -> {transition.after.sequence}")
                if transition.analysis_error:
                    print(f"  analysis error: {transition.analysis_error}")
                else:
                    _print_comparison_explanation(transition.before.source, transition.after.source, "  ")
        best = report.best_improvement
        if best is None:
            print("No material performance-oriented improvement detected across the snapshot timeline.")
            return 0
        print(f"Best improvement: snapshot {best.before.sequence} -> {best.after.sequence} (score: {best.score})")
        print(f"  events: {best.before.event} -> {best.after.event}")
        for change in best.changes:
            if change.is_meaningful:
                print(f"  {change.function}: {', '.join(change.reasons)}")
        return 0
    if args.command == "dataset":
        report = analyze_snapshots(SnapshotStore(args.store).load())
        spec = ExerciseSpec.from_dict(json.loads(args.spec.read_text(encoding="utf-8"))) if args.spec else None
        rows = export_timeline_jsonl(report, args.output, spec)
        print(f"Exported {len(rows)} transition feature rows to {args.output}.")
        return 0
    if args.command == "reviewed-dataset":
        rows = assemble_reviewed_dataset(args.stores, args.output)
        print(f"Assembled {len(rows)} reviewed transition rows from {len(args.stores)} store(s): {args.output}")
        return 0
    if args.command == "audit":
        rows = load_jsonl(args.dataset)
        report = audit_static_rules(rows)
        print(f"Reviewed transitions: {report.reviewed}")
        print(f"Static signals: {report.static_positive}; reviewed positives: {report.reviewed_positive}")
        print(f"True positives: {report.true_positive}; true negatives: {report.true_negative}")
        print(f"False positives: {report.false_positive}; false negatives: {report.false_negative}")
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(asdict(report), indent=2) + "\n", encoding="utf-8")
            print(f"Audit report: {args.output}")
        if args.details:
            for item in report.disagreements:
                print(f"  {item['outcome']}: {item['student_id']}/{item['attempt_id']} "
                      f"{item['from_snapshot']} -> {item['to_snapshot']} "
                      f"(score: {item['static_score']}, review: {item['review_decision']})")
        return 0
    if args.command == "demo":
        store = SnapshotStore(args.store)
        if store.manifest_path.exists():
            parser.error("demo store already exists; choose a new empty directory")
        slow = "def unique_sorted_groups(groups):\n    output = []\n    for group in groups:\n        for value in group:\n            output.append(value)\n        output.sort()\n    return output\n"
        intermediate = "def unique_sorted_groups(groups):\n    output = []\n    for group in groups:\n        for value in group:\n            output.append(value)\n    return sorted(output)\n"
        improved = "def unique_sorted_groups(groups):\n    output = set()\n    for group in groups:\n        output.update(group)\n    return sorted(output)\n"
        store.capture(slow, "compile")
        store.capture(intermediate, "compile")
        store.capture(improved, "submission")
        report = analyze_snapshots(store.load())
        output = args.store / "transition_features.jsonl"
        export_timeline_jsonl(report, output)
        best = report.best_improvement
        print(f"Created 3 snapshots. Best improvement: {best.before.sequence} -> {best.after.sequence} (score: {best.score}).")
        print(f"Feature dataset: {output}")
        return 0
    if args.command == "train":
        rows = load_jsonl(args.dataset)
        model = train(rows, labels_from_rows(rows, args.use_baseline_labels))
        model.save(args.model)
        print(f"Trained model on {len(rows)} labelled transitions: {args.model}")
        return 0
    if args.command == "predict":
        report = analyze_snapshots(SnapshotStore(args.store).load())
        spec = ExerciseSpec.from_dict(json.loads(args.spec.read_text(encoding="utf-8"))) if args.spec else None
        rows = [extract_transition_features(item, spec).to_dict() for item in report.transitions]
        if not rows:
            print("No snapshot transitions to score.")
            return 0
        model = LogisticRegressionModel.load(args.model)
        eligible = [(row, transition) for row, transition in zip(rows, report.transitions)
                    if row["is_eligible_improvement"]]
        if not eligible:
            print("No correctness-verified, structurally meaningful transitions to score.")
            return 0
        predictions = [(model.probability(row), row, transition) for row, transition in eligible]
        probability, best, _ = max(predictions, key=lambda item: item[0])
        print(f"Predicted best improvement: snapshot {best['from_snapshot']} -> {best['to_snapshot']} "
              f"(probability: {probability:.1%})")
        for score, row, transition in sorted(predictions, reverse=True, key=lambda item: item[0]):
            print(f"  {row['from_snapshot']} -> {row['to_snapshot']}: {score:.1%}")
            if args.explain:
                _print_comparison_explanation(transition.before.source, transition.after.source, "    ")
                _print_prediction_explanation(model, row, "    ")
        return 0
    before_source = args.before.read_text(encoding="utf-8")
    after_source = args.after.read_text(encoding="utf-8")
    changes = analyze_versions(before_source, after_source)
    if args.explain:
        _print_comparison_explanation(before_source, after_source)
    meaningful = [change for change in changes if change.is_meaningful]
    if not meaningful:
        print("No material performance-oriented improvements detected.")
        return 0
    for change in meaningful:
        print(f"{change.function} (confidence score: {change.score})")
        for reason in change.reasons:
            print(f"  - {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
