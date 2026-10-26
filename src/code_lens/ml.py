"""Small, transparent ML model for ranking code-change transitions.

This dependency-free binary logistic-regression classifier predicts whether a
transition is meaningful/best. The highest probability in a timeline wins.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

FEATURE_NAMES = (
    "matched_functions", "score", "loop_depth_change", "loop_count_change",
    "cyclomatic_complexity_change", "repeated_sort_change", "list_membership_change",
    "string_concat_change", "sliding_window_change", "before_pass_rate", "after_pass_rate", "correctness_change",
    "after_is_correct", "correctness_preserved", "runtime_change_percent", "before_growth_exponent",
    "after_growth_exponent", "growth_exponent_change",
)


@dataclass(frozen=True)
class LogisticRegressionModel:
    feature_names: tuple[str, ...]
    means: tuple[float, ...]
    scales: tuple[float, ...]
    weights: tuple[float, ...]
    bias: float

    def probability(self, row: dict[str, object]) -> float:
        values = _vector(row, self.feature_names)
        score = self.bias + sum(weight * ((value - mean) / scale)
                                for weight, value, mean, scale in zip(self.weights, values, self.means, self.scales))
        return _sigmoid(score)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "LogisticRegressionModel":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(tuple(data["feature_names"]), tuple(data["means"]), tuple(data["scales"]),
                   tuple(data["weights"]), data["bias"])


def train(rows: list[dict[str, object]], labels: list[int], epochs: int = 800,
          learning_rate: float = 0.12, l2: float = 0.01) -> LogisticRegressionModel:
    """Train standardised binary logistic regression using batch gradient descent."""
    if len(rows) != len(labels) or not rows:
        raise ValueError("training needs at least one row and one label per row")
    if len(set(labels)) != 2:
        raise ValueError("training needs both positive (1) and negative (0) labelled transitions")
    vectors = [_vector(row, FEATURE_NAMES) for row in rows]
    means = tuple(sum(vector[index] for vector in vectors) / len(vectors) for index in range(len(FEATURE_NAMES)))
    scales = tuple(max(1e-9, math.sqrt(sum((vector[index] - means[index]) ** 2 for vector in vectors) / len(vectors)))
                   for index in range(len(FEATURE_NAMES)))
    normalised = [[(value - mean) / scale for value, mean, scale in zip(vector, means, scales)] for vector in vectors]
    weights = [0.0] * len(FEATURE_NAMES)
    bias = 0.0
    for _ in range(epochs):
        errors = [_sigmoid(bias + sum(weight * value for weight, value in zip(weights, vector))) - label
                  for vector, label in zip(normalised, labels)]
        for index in range(len(weights)):
            gradient = sum(error * vector[index] for error, vector in zip(errors, normalised)) / len(rows)
            weights[index] -= learning_rate * (gradient + l2 * weights[index])
        bias -= learning_rate * sum(errors) / len(rows)
    return LogisticRegressionModel(FEATURE_NAMES, means, scales, tuple(weights), bias)


def load_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def labels_from_rows(rows: list[dict[str, object]], use_baseline_labels: bool = False) -> list[int]:
    """Read reviewer `label` values, or explicitly opt into bootstrap labels."""
    field = "baseline_label" if use_baseline_labels else "label"
    labels = []
    for row in rows:
        if field not in row:
            raise ValueError(f"missing '{field}'; add human labels or use --use-baseline-labels")
        value = row[field]
        if value in (1, True, "1", "best", "meaningful_improvement"):
            labels.append(1)
        elif value in (0, False, "0", "not_best", "not_meaningful"):
            labels.append(0)
        else:
            raise ValueError(f"unsupported label value: {value!r}")
    return labels


def _vector(row: dict[str, object], names: tuple[str, ...]) -> list[float]:
    return [0.0 if row.get(name) is None else float(row[name]) for name in names]


def _sigmoid(value: float) -> float:
    return 1 / (1 + math.exp(-max(-500.0, min(500.0, value))))
