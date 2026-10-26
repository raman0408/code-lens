from __future__ import annotations

import argparse
from pathlib import Path

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
