from __future__ import annotations

import argparse
import json
from pathlib import Path

from .evaluation import ExerciseSpec
from .features import export_timeline_jsonl, extract_transition_features
from .ml import LogisticRegressionModel, labels_from_rows, load_jsonl, train
from .model import analyze_versions
from .snapshots import SnapshotStore, analyze_snapshots


def main() -> int:
    parser = argparse.ArgumentParser(description="Find likely performance improvements between Python files.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    compare = subparsers.add_parser("compare", help="compare before.py to after.py")
    compare.add_argument("before", type=Path)
    compare.add_argument("after", type=Path)
    capture = subparsers.add_parser("capture", help="record a source snapshot after a compile or submission")
    capture.add_argument("store", type=Path, help="directory for this student's snapshot timeline")
    capture.add_argument("source", type=Path)
    capture.add_argument("--event", choices=("compile", "submission"), required=True)
    timeline = subparsers.add_parser("timeline", help="analyze every consecutive snapshot in a store")
    timeline.add_argument("store", type=Path)
    dataset = subparsers.add_parser("dataset", help="export ML-ready transition features as JSONL")
    dataset.add_argument("store", type=Path)
    dataset.add_argument("output", type=Path)
    dataset.add_argument("--spec", type=Path, help="exercise tests and benchmark configuration")
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
    args = parser.parse_args()
    if args.command == "capture":
        snapshot = SnapshotStore(args.store).capture(args.source.read_text(encoding="utf-8"), args.event)
        print(f"Captured snapshot {snapshot.sequence} ({snapshot.event}, {snapshot.source_hash[:12]}).")
        return 0
    if args.command == "timeline":
        report = analyze_snapshots(SnapshotStore(args.store).load())
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
        predictions = [(model.probability(row), row) for row in rows]
        probability, best = max(predictions, key=lambda item: item[0])
        print(f"Predicted best improvement: snapshot {best['from_snapshot']} -> {best['to_snapshot']} "
              f"(probability: {probability:.1%})")
        for score, row in sorted(predictions, reverse=True, key=lambda item: item[0]):
            print(f"  {row['from_snapshot']} -> {row['to_snapshot']}: {score:.1%}")
        return 0
    changes = analyze_versions(args.before.read_text(encoding="utf-8"), args.after.read_text(encoding="utf-8"))
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
