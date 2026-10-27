"""Build a reviewed, profile-driven synthetic cohort for pipeline development.

The generated records are intentionally synthetic.  They exercise the data
pipeline and are never a substitute for independently reviewed human data.
Each profile uses a different learning trajectory; variants select different
valid implementations and intermediate mistakes rather than copying a single
timeline under new student IDs.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from code_lens.evaluation import ExerciseSpec
from code_lens.features import assemble_reviewed_dataset, audit_static_rules, export_timeline_jsonl
from code_lens.snapshots import SnapshotStore, analyze_snapshots


STANDARD = "correctness_preserved_and_asymptotic_complexity_improved"
ATTEMPT_ID = "minimum-size-subarray-sum"
PROFILES = (
    "gradual_trial_and_error",
    "no_clue_to_mediocre",
    "correct_then_optimized",
    "brute_force_to_optimal",
    "frequent_delete_and_retry",
    "optimal_with_edge_case_errors",
    "syntax_struggles",
    "average_case_struggles",
    "perfect_improver",
)


@dataclass(frozen=True)
class Review:
    label: int
    decision: str
    reason: str


def _quadratic(variant: int) -> str:
    sources = (
        "def min_subarray_len(target, nums):\n"
        "    best = len(nums) + 1\n"
        "    for start in range(len(nums)):\n"
        "        total = 0\n"
        "        for end in range(start, len(nums)):\n"
        "            total += nums[end]\n"
        "            if total >= target:\n"
        "                best = min(best, end - start + 1)\n"
        "                break\n"
        "    return 0 if best == len(nums) + 1 else best\n",
        "def min_subarray_len(target, nums):\n"
        "    answer = len(nums) + 1\n"
        "    for left in range(len(nums)):\n"
        "        running = 0\n"
        "        for right in range(left, len(nums)):\n"
        "            running += nums[right]\n"
        "            if running >= target:\n"
        "                answer = min(answer, right - left + 1)\n"
        "    return answer if answer <= len(nums) else 0\n",
        "def min_subarray_len(target, nums):\n"
        "    candidates = []\n"
        "    for start in range(len(nums)):\n"
        "        total = 0\n"
        "        for end in range(start, len(nums)):\n"
        "            total += nums[end]\n"
        "            if total >= target:\n"
        "                candidates.append(end - start + 1)\n"
        "                break\n"
        "    return min(candidates) if candidates else 0\n",
    )
    return sources[variant % len(sources)]


def _sliding_window(variant: int) -> str:
    sources = (
        "def min_subarray_len(target, nums):\n"
        "    left = total = 0\n"
        "    best = len(nums) + 1\n"
        "    for right, value in enumerate(nums):\n"
        "        total += value\n"
        "        while total >= target:\n"
        "            best = min(best, right - left + 1)\n"
        "            total -= nums[left]\n"
        "            left += 1\n"
        "    return 0 if best == len(nums) + 1 else best\n",
        "def min_subarray_len(target, nums):\n"
        "    start = 0\n"
        "    running = 0\n"
        "    answer = len(nums) + 1\n"
        "    for end in range(len(nums)):\n"
        "        running += nums[end]\n"
        "        while running >= target:\n"
        "            answer = min(answer, end - start + 1)\n"
        "            running -= nums[start]\n"
        "            start += 1\n"
        "    return answer if answer <= len(nums) else 0\n",
        "def min_subarray_len(target, nums):\n"
        "    best = float('inf')\n"
        "    left = total = 0\n"
        "    for right, value in enumerate(nums):\n"
        "        total += value\n"
        "        while total >= target:\n"
        "            best = min(best, right - left + 1)\n"
        "            total -= nums[left]\n"
        "            left += 1\n"
        "    return 0 if best == float('inf') else best\n",
    )
    return sources[variant % len(sources)]


def _prefix_binary_search() -> str:
    """A correct O(n log n) baseline distinct from the brute-force profile."""
    return (
        "from bisect import bisect_left\n\n"
        "def min_subarray_len(target, nums):\n"
        "    prefix = [0]\n"
        "    for value in nums:\n"
        "        prefix.append(prefix[-1] + value)\n"
        "    best = len(nums) + 1\n"
        "    for start in range(len(nums)):\n"
        "        end = bisect_left(prefix, prefix[start] + target, start + 1)\n"
        "        if end <= len(nums):\n"
        "            best = min(best, end - start)\n"
        "    return 0 if best == len(nums) + 1 else best\n"
    )


def _profile_timeline(profile: str, variant: int) -> tuple[list[str], list[Review]]:
    quadratic = _quadratic(variant)
    alternate_quadratic = _quadratic(variant + 1)
    sliding = _sliding_window(variant)
    bad_syntax = "def min_subarray_len(target, nums)\n    return 0\n"
    unfinished = "def min_subarray_len(target, nums):\n    for value in nums:\n"
    always_zero = "def min_subarray_len(target, nums):\n    return 0\n"
    average_case_mistake = (
        "def min_subarray_len(target, nums):\n"
        "    for value in nums:\n"
        "        if value >= target:\n"
        "            return 1\n"
        "    return 0\n"
    )
    edge_case_mistake = (
        "def min_subarray_len(target, nums):\n"
        "    left = total = 0\n"
        "    best = len(nums) + 1\n"
        "    for right, value in enumerate(nums):\n"
        "        total += value\n"
        "        while total >= target:\n"
        "            best = min(best, right - left + 1)\n"
        "            total -= nums[left]\n"
        "            left += 1\n"
        "    return best\n"
    )
    no = lambda decision, reason: Review(0, decision, reason)
    yes = lambda reason: Review(1, "asymptotic_improvement", reason)
    if profile == "gradual_trial_and_error":
        return [always_zero, quadratic, sliding], [
            no("correctness_fix_only", "A correct quadratic solution replaces an incorrect placeholder."),
            yes("A correct nested scan becomes a linear sliding window."),
        ]
    if profile == "no_clue_to_mediocre":
        return [bad_syntax, always_zero, average_case_mistake, quadratic], [
            no("syntax_fix_only", "The snapshot becomes parseable but remains incorrect."),
            no("incorrect", "The implementation handles only a narrow average case."),
            no("correct_but_quadratic", "The final implementation is correct but remains O(n squared)."),
        ]
    if profile == "correct_then_optimized":
        return [quadratic, alternate_quadratic, sliding], [
            no("correct_refactor_only", "Both correct versions retain quadratic search."),
            yes("A correct quadratic solution is replaced by a sliding window."),
        ]
    if profile == "brute_force_to_optimal":
        return [quadratic, sliding], [
            yes("A correct brute-force scan is replaced by a linear sliding window."),
        ]
    if profile == "frequent_delete_and_retry":
        return [bad_syntax, unfinished, always_zero, quadratic, sliding], [
            no("syntax_churn", "The second attempt is still incomplete Python."),
            no("syntax_fix_only", "The code parses but always returns zero."),
            no("correct_but_quadratic", "A correct but quadratic solution is recovered."),
            yes("The recovered quadratic algorithm is replaced by a linear one."),
        ]
    if profile == "optimal_with_edge_case_errors":
        return [edge_case_mistake, sliding], [
            no("correctness_fix_only", "The algorithm is already linear; this fixes the no-solution edge case."),
        ]
    if profile == "syntax_struggles":
        return [bad_syntax, unfinished, quadratic], [
            no("syntax_churn", "The second snapshot remains invalid Python."),
            no("syntax_fix_to_quadratic", "The final version is correct but quadratic."),
        ]
    if profile == "average_case_struggles":
        return [always_zero, average_case_mistake, quadratic], [
            no("incorrect", "The implementation only recognizes one-element answers."),
            no("correct_but_quadratic", "The final version is correct but not optimized."),
        ]
    if profile == "perfect_improver":
        return [_prefix_binary_search(), sliding], [
            yes("Correct prefix-sum binary search improves from O(n log n) to a linear sliding window."),
        ]
    raise ValueError(f"unknown profile: {profile}")


def _spec() -> dict[str, object]:
    return {
        "function_name": "min_subarray_len",
        "tests": [
            {"args": [7, [2, 3, 1, 2, 4, 3]], "expected": 2},
            {"args": [4, [1, 4, 4]], "expected": 1},
            {"args": [11, [1, 1, 1, 1, 1, 1, 1, 1]], "expected": 0},
            {"args": [15, [5, 1, 3, 5, 10, 7, 4, 9, 2, 8]], "expected": 2},
        ],
        "benchmark_series": [{"name": "items", "cases": [
            {"size": size, "args": [size + 1, [1] * size]} for size in (32, 64, 128)
        ]}],
        "benchmark_repeats": 10,
    }


def _write_attempt(root: Path, student_id: str, profile: str, variant: int, seed: int) -> None:
    directory = root / student_id / ATTEMPT_ID
    if directory.exists():
        raise FileExistsError(f"refusing to overwrite existing attempt: {directory}")
    # The seed selects among authored, semantically equivalent source variants;
    # it never randomizes labels or fabricates an unreviewed trajectory.
    sources, reviews = _profile_timeline(profile, seed + variant)
    spec_data = _spec()
    directory.mkdir(parents=True)
    (directory / "exercise_spec.json").write_text(json.dumps(spec_data, indent=2) + "\n", encoding="utf-8")
    metadata = {
        "dataset_source": "synthetic_codex_profile_cohort",
        "student_id": student_id,
        "attempt_id": ATTEMPT_ID,
        "learner_profile": profile,
        "profile_variant": variant,
        "generation_seed": seed,
        "problem_reference": {"provider": "LeetCode", "number": 209, "title": "Minimum Size Subarray Sum"},
        "function_name": "min_subarray_len",
        "language": "python",
        "snapshot_count": len(sources),
        "label_status": "synthetic_profile_review",
        "review_standard": "A positive label requires full after-version correctness, no regression, and a material asymptotic complexity improvement.",
        "notes": "Profile-authored synthetic timeline for pipeline development; not human behaviour or ML evaluation evidence.",
    }
    (directory / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    store = SnapshotStore(directory)
    for index, source in enumerate(sources):
        store.capture(source, "submission" if index == len(sources) - 1 else "compile")
    labels = []
    for sequence, review in enumerate(reviews, 1):
        labels.append({
            "from_snapshot": sequence, "to_snapshot": sequence + 1,
            "label": review.label, "decision": review.decision, "reason": review.reason,
            "reviewer": "synthetic-profile-author", "review_standard": STANDARD,
        })
    (directory / "gold_labels.jsonl").write_text(
        "".join(json.dumps(label) + "\n" for label in labels), encoding="utf-8"
    )
    report = analyze_snapshots(store.load())
    export_timeline_jsonl(report, directory / "transitions.jsonl", ExerciseSpec.from_dict(spec_data))


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a profile-driven synthetic Code Lens cohort.")
    parser.add_argument("--output-root", type=Path, default=Path("data/synthetic_codex/cohorts"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--variants-per-profile", type=int, default=3)
    parser.add_argument("--profiles", nargs="+", choices=PROFILES, default=list(PROFILES))
    args = parser.parse_args()
    if args.variants_per_profile < 1:
        parser.error("--variants-per-profile must be positive")
    cohort_root = args.output_root / f"cohort-seed-{args.seed}"
    if cohort_root.exists():
        parser.error(f"cohort already exists: {cohort_root}; choose another seed or output root")
    cohort_root.mkdir(parents=True)
    student_number = 1
    attempts = []
    for profile in args.profiles:
        for variant in range(args.variants_per_profile):
            student_id = f"student-{student_number:03d}"
            _write_attempt(cohort_root, student_id, profile, variant, args.seed)
            attempts.append(cohort_root / student_id / ATTEMPT_ID)
            student_number += 1
    reviewed_rows = assemble_reviewed_dataset(attempts, cohort_root / "reviewed-transitions.jsonl")
    audit = audit_static_rules(reviewed_rows)
    (cohort_root / "static-rule-audit.json").write_text(
        json.dumps(asdict(audit), indent=2) + "\n", encoding="utf-8"
    )
    manifest = {
        "dataset_source": "synthetic_codex_profile_cohort",
        "generation_seed": args.seed,
        "profiles": args.profiles,
        "variants_per_profile": args.variants_per_profile,
        "student_count": student_number - 1,
        "warning": "Synthetic profile data is not independent human behaviour and is not valid ML evaluation evidence.",
    }
    (cohort_root / "cohort_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Created {student_number - 1} profile-authored synthetic students: {cohort_root}")
    print(f"Reviewed transitions: {len(reviewed_rows)}; audit: {cohort_root / 'static-rule-audit.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
