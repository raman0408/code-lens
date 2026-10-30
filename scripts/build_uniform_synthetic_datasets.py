"""Build the complete, split-safe synthetic corpus for Code Lens.

Every generated learner attempts the same five defined problems.  Student IDs,
profile variants, and source hashes are tier-specific; the final-test cohort is
created once and marked sealed.  This script refuses to overwrite a cohort.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from code_lens.evaluation import ExerciseSpec
from code_lens.features import assemble_reviewed_dataset, audit_static_rules, export_timeline_jsonl
from code_lens.snapshots import SnapshotStore, analyze_snapshots


PROBLEMS = (7, 55, 58, 189, 209)
PROBLEM_SLUGS = ("reverse-integer", "jump-game", "length-of-last-word", "rotate-array",
                 "minimum-size-subarray-sum")
TIER_CONFIG = {
    "development": ("dev", 1, 101),
    "training": ("train", 3, 202),
    "validation": ("validation", 2, 303),
    "final-test": ("final", 2, 404),
}


def _build_student(root: Path, tier: str, student_id: str, variant: int) -> None:
    command = [
        sys.executable, "scripts/build_synthetic_batch.py", "--output-root", str(root),
        "--student-id", student_id, "--dataset-tier", tier, "--variant", str(variant),
        "--problems", *(str(number) for number in PROBLEMS),
    ]
    subprocess.run(command, check=True)


def build_tier(dataset_root: Path, tier: str) -> Path:
    prefix, student_count, seed = TIER_CONFIG[tier]
    cohort_root = dataset_root / tier / f"uniform-five-problem-seed-{seed}"
    if cohort_root.exists():
        raise FileExistsError(f"refusing to overwrite existing cohort: {cohort_root}")
    cohort_root.mkdir(parents=True)
    attempts: list[Path] = []
    for index in range(1, student_count + 1):
        student_id = f"{prefix}-{index:03d}"
        _build_student(cohort_root, tier, student_id, seed + index)
        for slug in PROBLEM_SLUGS:
            attempt = cohort_root / student_id / slug
            spec = ExerciseSpec.from_dict(json.loads((attempt / "exercise_spec.json").read_text(encoding="utf-8")))
            export_timeline_jsonl(analyze_snapshots(SnapshotStore(attempt).load()), attempt / "transitions.jsonl", spec)
            attempts.append(attempt)
    reviewed = assemble_reviewed_dataset(attempts, cohort_root / "reviewed-transitions.jsonl")
    audit = audit_static_rules(reviewed)
    (cohort_root / "static-rule-audit.json").write_text(json.dumps(asdict(audit), indent=2) + "\n", encoding="utf-8")
    (cohort_root / "cohort_manifest.json").write_text(json.dumps({
        "dataset_source": "uniform_synthetic_codex",
        "dataset_tier": tier,
        "generation_seed": seed,
        "student_count": student_count,
        "problems": list(PROBLEMS),
        "attempts_per_student": len(PROBLEMS),
        "sealed": tier == "final-test",
        "warning": "Synthetic-only integration corpus; not evidence of real learner behaviour.",
    }, indent=2) + "\n", encoding="utf-8")
    return cohort_root


def _update_tier_manifest(dataset_root: Path, tier: str, cohort: Path) -> None:
    manifest_path = dataset_root / tier / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update({
        "status": "sealed_synthetic" if tier == "final-test" else "active_synthetic",
        "student_count": TIER_CONFIG[tier][1],
        "sources": [str(cohort).replace("\\", "/")],
        "generation_seed": TIER_CONFIG[tier][2],
        "problems": list(PROBLEMS),
    })
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build fresh uniform five-problem synthetic dataset tiers.")
    parser.add_argument("--dataset-root", type=Path, default=Path("data/datasets"))
    parser.add_argument("--tiers", nargs="+", choices=tuple(TIER_CONFIG),
                        default=("development", "training", "validation", "final-test"))
    args = parser.parse_args()
    for tier in args.tiers:
        cohort = build_tier(args.dataset_root, tier)
        _update_tier_manifest(args.dataset_root, tier, cohort)
        print(f"Created {tier} cohort: {cohort}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
