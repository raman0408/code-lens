"""Correctness and timing hooks used to create ML training features.

This is a development-time harness, not a security sandbox. Never execute
untrusted student code in the host process in a production deployment.
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class ExerciseSpec:
    function_name: str
    tests: tuple[tuple[list[object], object], ...]
    benchmark_args: tuple[list[object], ...] = ()
    benchmark_repeats: int = 5

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "ExerciseSpec":
        tests = tuple((item["args"], item["expected"]) for item in data.get("tests", []))
        return cls(
            function_name=data["function_name"], tests=tests,
            benchmark_args=tuple(data.get("benchmark_args", [])),
            benchmark_repeats=data.get("benchmark_repeats", 5),
        )


@dataclass(frozen=True)
class EvaluationResult:
    passed: int
    total: int
    median_runtime_ms: float | None
    error: str | None = None

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 1.0


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
    for args in payload["benchmark_args"]:
        started = time.perf_counter()
        for _ in range(payload["benchmark_repeats"]):
            function(*args)
        timings.append((time.perf_counter() - started) * 1000 / payload["benchmark_repeats"])
    print(json.dumps({"outcomes": outcomes, "timings": timings}))
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
    return EvaluationResult(sum(result["outcomes"]), len(spec.tests),
                            statistics.median(timings) if timings else None)
