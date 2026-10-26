import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from code_lens.model import analyze_source, analyze_versions
from code_lens.evaluation import BenchmarkSeries, ExerciseSpec, evaluate_source
from code_lens.features import (assemble_reviewed_dataset, audit_static_rules, export_timeline_jsonl,
                                 extract_transition_features)
from code_lens.ml import LogisticRegressionModel, labels_from_rows, train
from code_lens.snapshots import SnapshotStore, analyze_snapshots


class AnalysisModelTests(unittest.TestCase):
    def test_extracts_nested_loop_metrics(self):
        analysis = analyze_source("def work(items):\n    for item in items:\n        for value in item:\n            if value:\n                pass\n")
        metrics = analysis.functions["work"]
        self.assertEqual(metrics.loop_count, 2)
        self.assertEqual(metrics.max_loop_depth, 2)
        self.assertEqual(metrics.cyclomatic_complexity, 4)

    def test_attributes_reduced_nesting_and_sorting(self):
        before = "def rank(groups):\n    result = []\n    for group in groups:\n        for value in group:\n            result.append(value)\n        result.sort()\n    return result\n"
        after = "def rank(groups):\n    result = []\n    for group in groups:\n        result.extend(group)\n    return sorted(result)\n"
        changes = analyze_versions(before, after)
        self.assertEqual(changes[0].function, "rank")
        self.assertTrue(changes[0].is_meaningful)
        self.assertIn("moved or removed sorting from a loop", changes[0].reasons)

    def test_counts_only_known_string_concatenation_in_a_loop(self):
        source = "def work(items):\n    text = ''\n    total = 0\n    for item in items:\n        text += item\n        total += 1\n    return text, total\n"
        metrics = analyze_source(source).functions["work"]
        self.assertEqual(metrics.string_concat_in_loop, 1)

    def test_detects_conservative_sliding_window_pattern(self):
        before = "def smallest(target, values):\n    best = len(values) + 1\n    for left in range(len(values)):\n        total = 0\n        for right in range(left, len(values)):\n            total += values[right]\n            if total >= target:\n                best = min(best, right - left + 1)\n                break\n    return best\n"
        after = "def smallest(target, values):\n    left = total = 0\n    best = len(values) + 1\n    for right, value in enumerate(values):\n        total += value\n        while total >= target:\n            best = min(best, right - left + 1)\n            total -= values[left]\n            left += 1\n    return best\n"
        changes = analyze_versions(before, after)
        self.assertIn("introduced an expand/shrink sliding-window pattern", changes[0].reasons)
        self.assertTrue(changes[0].is_meaningful)

    def test_ignores_unmatched_functions(self):
        self.assertEqual(analyze_versions("def old(): pass", "def new(): pass"), [])

    def test_timeline_finds_exact_best_transition(self):
        slow = "def work(groups):\n    result = []\n    for group in groups:\n        for value in group:\n            result.append(value)\n        result.sort()\n    return result\n"
        neutral = "def work(groups):\n    result = []\n    for group in groups:\n        for value in group:\n            result.append(value)\n        result.sort()\n    return list(result)\n"
        improved = "def work(groups):\n    result = []\n    for group in groups:\n        result.extend(group)\n    return sorted(result)\n"
        with TemporaryDirectory() as directory:
            store = SnapshotStore(Path(directory) / "student-1")
            store.capture(slow, "compile")
            store.capture(neutral, "compile")
            store.capture(improved, "submission")
            report = analyze_snapshots(store.load())
        self.assertEqual(len(report.transitions), 2)
        self.assertEqual(report.best_improvement.before.sequence, 2)
        self.assertEqual(report.best_improvement.after.sequence, 3)
        self.assertGreaterEqual(report.best_improvement.score, 3)

    def test_timeline_keeps_invalid_compile_snapshot(self):
        with TemporaryDirectory() as directory:
            store = SnapshotStore(Path(directory) / "student-1")
            store.capture("def work(:\n", "compile")
            store.capture("def work():\n    return 1\n", "submission")
            report = analyze_snapshots(store.load())
        self.assertEqual(len(report.transitions), 1)
        self.assertIn("invalid Python", report.transitions[0].analysis_error)

    def test_extracts_features_and_exports_jsonl(self):
        before = "def total(items):\n    value = 0\n    for item in items:\n        for other in items:\n            value += item + other\n    return value\n"
        after = "def total(items):\n    value = sum(items)\n    return value * len(items) + value * len(items)\n"
        with TemporaryDirectory() as directory:
            store = SnapshotStore(Path(directory) / "student-1")
            store.capture(before, "compile")
            store.capture(after, "submission")
            report = analyze_snapshots(store.load())
            row = extract_transition_features(report.transitions[0])
            destination = Path(directory) / "features.jsonl"
            export_timeline_jsonl(report, destination)
            saved = destination.read_text(encoding="utf-8")
        self.assertEqual(row.loop_depth_change, -2)
        self.assertEqual(row.baseline_label, "not_meaningful")
        self.assertFalse(row.is_eligible_improvement)
        self.assertIn('"from_snapshot": 1', saved)

    def test_eligible_improvement_must_be_correct_and_non_regressive(self):
        before = "def all_positive(values):\n    result = True\n    for value in values:\n        for copy in (value,):\n            if copy <= 0:\n                result = False\n    return result\n"
        after = "def all_positive(values):\n    return all(value > 0 for value in values)\n"
        spec = ExerciseSpec("all_positive", (([[1, 2]], True), ([[-1, 2]], False)))
        with TemporaryDirectory() as directory:
            store = SnapshotStore(Path(directory) / "student-1")
            store.capture(before, "compile")
            store.capture(after, "submission")
            row = extract_transition_features(analyze_snapshots(store.load()).transitions[0], spec)
        self.assertTrue(row.after_is_correct)
        self.assertTrue(row.correctness_preserved)
        self.assertTrue(row.is_eligible_improvement)

    def test_incorrect_after_version_is_not_an_eligible_improvement(self):
        before = "def all_positive(values):\n    result = True\n    for value in values:\n        for copy in (value,):\n            if copy <= 0:\n                result = False\n    return result\n"
        after = "def all_positive(values):\n    return True\n"
        spec = ExerciseSpec("all_positive", (([[1, 2]], True), ([[-1, 2]], False)))
        with TemporaryDirectory() as directory:
            store = SnapshotStore(Path(directory) / "student-1")
            store.capture(before, "compile")
            store.capture(after, "submission")
            row = extract_transition_features(analyze_snapshots(store.load()).transitions[0], spec)
        self.assertFalse(row.after_is_correct)
        self.assertFalse(row.is_eligible_improvement)

    def test_evaluation_runs_tests_and_benchmark(self):
        spec = ExerciseSpec("double", (([2], 4), ([3], 6)), ([100],), 2)
        result = evaluate_source("def double(value):\n    return value * 2\n", spec)
        self.assertEqual(result.pass_rate, 1.0)
        self.assertIsNotNone(result.median_runtime_ms)

    def test_evaluation_records_multi_size_growth(self):
        series = BenchmarkSeries("items", ((10, [[1] * 10]), (100, [[1] * 100])))
        spec = ExerciseSpec("total", (([[1, 2]], 3),), (), (series,), 50)
        result = evaluate_source("def total(values):\n    return sum(values)\n", spec)
        self.assertEqual(result.pass_rate, 1.0)
        self.assertEqual(len(result.series_timings_ms), 2)
        self.assertIsNotNone(result.growth_exponent)

    def test_assembles_and_audits_reviewed_dataset(self):
        with TemporaryDirectory() as directory:
            store = Path(directory) / "student-1" / "attempt-1"
            store.mkdir(parents=True)
            (store / "metadata.json").write_text(json.dumps({
                "dataset_source": "synthetic", "student_id": "student-1", "attempt_id": "attempt-1",
                "language": "python", "problem_reference": {"number": 1, "title": "Example"},
            }), encoding="utf-8")
            (store / "transitions.jsonl").write_text(
                '{"from_snapshot": 1, "to_snapshot": 2, "score": 4}\n'
                '{"from_snapshot": 2, "to_snapshot": 3, "score": 0}\n', encoding="utf-8")
            (store / "gold_labels.jsonl").write_text(
                '{"from_snapshot": 1, "to_snapshot": 2, "label": 0, "decision": "refactor"}\n'
                '{"from_snapshot": 2, "to_snapshot": 3, "label": 1, "decision": "algorithm"}\n', encoding="utf-8")
            destination = Path(directory) / "reviewed.jsonl"
            rows = assemble_reviewed_dataset([store], destination)
            report = audit_static_rules(rows)
        self.assertEqual(len(rows), 2)
        self.assertEqual(report.false_positive, 1)
        self.assertEqual(report.false_negative, 1)

    def test_trains_and_serializes_ml_classifier(self):
        rows = [
            {"matched_functions": 1, "score": 0, "loop_depth_change": 0, "loop_count_change": 0,
             "cyclomatic_complexity_change": 0, "repeated_sort_change": 0, "list_membership_change": 0,
             "string_concat_change": 0, "correctness_change": 0, "runtime_change_percent": 5, "label": 0},
            {"matched_functions": 1, "score": 8, "loop_depth_change": -1, "loop_count_change": -1,
             "cyclomatic_complexity_change": -2, "repeated_sort_change": -1, "list_membership_change": 0,
             "string_concat_change": 0, "correctness_change": 0, "runtime_change_percent": -60, "label": 1},
        ]
        model = train(rows, labels_from_rows(rows), epochs=300)
        self.assertGreater(model.probability(rows[1]), model.probability(rows[0]))
        with TemporaryDirectory() as directory:
            path = Path(directory) / "model.json"
            model.save(path)
            restored = LogisticRegressionModel.load(path)
        self.assertAlmostEqual(restored.probability(rows[1]), model.probability(rows[1]))


if __name__ == "__main__":
    unittest.main()
