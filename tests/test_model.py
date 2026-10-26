import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from code_lens.model import analyze_source, analyze_versions
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


if __name__ == "__main__":
    unittest.main()
