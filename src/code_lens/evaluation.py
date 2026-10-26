"""Correctness and timing hooks used to create ML training features.

This is a development-time harness, not a security sandbox. Never execute
untrusted student code in the host process in a production deployment.
"""

from __future__ import annotations

import json
import math
import statistics
import subprocess
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class BenchmarkSeries:
    name: str
    cases: tuple[tuple[int, list[object]], ...]

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "BenchmarkSeries":
        return cls(data["name"], tuple((item["size"], item["args"]) for item in data["cases"]))


@dataclass(frozen=True)
class ExerciseSpec:
    function_name: str
    tests: tuple[tuple[list[object], object], ...]
    benchmark_args: tuple[list[object], ...] = ()
    benchmark_series: tuple[BenchmarkSeries, ...] = ()
    benchmark_repeats: int = 5

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "ExerciseSpec":
        tests = tuple((item["args"], item["expected"]) for item in data.get("tests", []))
        return cls(
            function_name=data["function_name"], tests=tests,
            benchmark_args=tuple(data.get("benchmark_args", [])),
            benchmark_series=tuple(BenchmarkSeries.from_dict(item) for item in data.get("benchmark_series", [])),
            benchmark_repeats=data.get("benchmark_repeats", 5),
        )


@dataclass(frozen=True)
class EvaluationResult:
    passed: int
    total: int
    median_runtime_ms: float | None
    error: str | None = None
    series_timings_ms: tuple[tuple[str, int, float], ...] = ()

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 1.0

    @property
    def is_correct(self) -> bool:
        """True only when every required test passed without an evaluation error."""
        return self.error is None and self.passed == self.total

    @property
    def growth_exponent(self) -> float | None:
        """Median log-log slope across benchmark series, when size data exists."""
        slopes = []
        by_name: dict[str, list[tuple[int, float]]] = {}
        for name, size, runtime in self.series_timings_ms:
            by_name.setdefault(name, []).append((size, runtime))
        for measurements in by_name.values():
            first, last = min(measurements), max(measurements)
            if first[0] > 0 and first[1] > 0 and last[0] > first[0] and last[1] > 0:
                slopes.append(math.log(last[1] / first[1]) / math.log(last[0] / first[0]))
        return statistics.median(slopes) if slopes else None


_RUNNER = r'''
import json, sys, time
payload = json.load(sys.stdin)
namespace = {"__name__": "student_solution"}
try:
    exec(compile(payload["source"], "student_submission.py", "exec"), namespace)
    function = namespace[payload["function_name"]]
    outcomes = []
    for test in payload["tests"]:
        outcomes.append(function(*test["args"]) == test["expected"])
    timings = []
    series_timings = []
    if all(outcomes):
        for args in payload["benchmark_args"]:
            started = time.perf_counter()
            for _ in range(payload["benchmark_repeats"]):
                function(*args)
            timings.append((time.perf_counter() - started) * 1000 / payload["benchmark_repeats"])
        for series in payload["benchmark_series"]:
            for case in series["cases"]:
                started = time.perf_counter()
                for _ in range(payload["benchmark_repeats"]):
                    function(*case["args"])
                series_timings.append({"name": series["name"], "size": case["size"],
                                       "runtime_ms": (time.perf_counter() - started) * 1000 / payload["benchmark_repeats"]})
    print(json.dumps({"outcomes": outcomes, "timings": timings, "series_timings": series_timings}))
except Exception as error:
    print(json.dumps({"error": f"{type(error).__name__}: {error}"}))
'''


def evaluate_source(source: str, spec: ExerciseSpec, timeout_seconds: float = 3.0) -> EvaluationResult:
    """Run instructor-supplied examples and benchmarks in a separate process."""
    payload = {
        "source": source,
        "function_name": spec.function_name,
        "tests": [{"args": args, "expected": expected} for args, expected in spec.tests],
        "benchmark_args": list(spec.benchmark_args),
        "benchmark_series": [{"name": series.name, "cases": [
            {"size": size, "args": args} for size, args in series.cases
        ]} for series in spec.benchmark_series],
        "benchmark_repeats": spec.benchmark_repeats,
    }
    try:
        completed = subprocess.run(
            [sys.executable, "-c", _RUNNER], input=json.dumps(payload), text=True,
            capture_output=True, timeout=timeout_seconds, check=False,
        )
    except subprocess.TimeoutExpired:
        return EvaluationResult(0, len(spec.tests), None, "evaluation timed out")
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return EvaluationResult(0, len(spec.tests), None, "evaluation produced no valid result")
    if "error" in result:
        return EvaluationResult(0, len(spec.tests), None, result["error"])
    timings = result["timings"]
    series_timings = tuple((item["name"], item["size"], item["runtime_ms"])
                           for item in result.get("series_timings", []))
    return EvaluationResult(sum(result["outcomes"]), len(spec.tests),
                            statistics.median(timings) if timings else None,
                            series_timings_ms=series_timings)
