"""A transparent, non-LLM model for performance-oriented change attribution."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class FunctionMetrics:
    name: str
    line: int
    cyclomatic_complexity: int
    loop_count: int
    max_loop_depth: int
    repeated_sort_calls: int
    list_membership_checks: int
    string_concat_in_loop: int


@dataclass(frozen=True)
class ProgramAnalysis:
    functions: dict[str, FunctionMetrics]


@dataclass(frozen=True)
class ChangeAttribution:
    function: str
    score: int
    reasons: tuple[str, ...]
    before: FunctionMetrics
    after: FunctionMetrics

    @property
    def is_meaningful(self) -> bool:
        return self.score >= 3

    @property
    def evidence(self) -> tuple[tuple[int, str], ...]:
        """The individual rules and points that produced ``score``.

        Keeping this alongside the short ``reasons`` view lets command-line
        users inspect a result instead of treating its score as a black box.
        """
        return tuple(_reasons(self.before, self.after))


class _FunctionVisitor(ast.NodeVisitor):
    def __init__(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.node = node
        self.complexity = 1
        self.loop_count = 0
        self.loop_depth = 0
        self.max_loop_depth = 0
        self.repeated_sort_calls = 0
        self.list_membership_checks = 0
        self.string_concat_in_loop = 0

    def visit_If(self, node: ast.If) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_IfExp(self, node: ast.IfExp) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        self.complexity += max(0, len(node.values) - 1)
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def _visit_loop(self, node: ast.AST) -> None:
        self.complexity += 1
        self.loop_count += 1
        self.loop_depth += 1
        self.max_loop_depth = max(self.max_loop_depth, self.loop_depth)
        self.generic_visit(node)
        self.loop_depth -= 1

    def visit_For(self, node: ast.For) -> None:
        self._visit_loop(node)

    def visit_While(self, node: ast.While) -> None:
        self._visit_loop(node)

    def visit_Call(self, node: ast.Call) -> None:
        if self.loop_depth and isinstance(node.func, ast.Attribute) and node.func.attr == "sort":
            self.repeated_sort_calls += 1
        if self.loop_depth and isinstance(node.func, ast.Name) and node.func.id == "sorted":
            self.repeated_sort_calls += 1
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        if self.loop_depth and any(isinstance(op, (ast.In, ast.NotIn)) for op in node.ops):
            if any(isinstance(value, (ast.List, ast.ListComp)) for value in node.comparators):
                self.list_membership_checks += 1
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        if self.loop_depth and isinstance(node.op, ast.Add) and isinstance(node.value, (ast.Constant, ast.JoinedStr)):
            self.string_concat_in_loop += 1
        self.generic_visit(node)

    def metrics(self) -> FunctionMetrics:
        return FunctionMetrics(self.node.name, self.node.lineno, self.complexity, self.loop_count,
                               self.max_loop_depth, self.repeated_sort_calls,
                               self.list_membership_checks, self.string_concat_in_loop)


def analyze_source(source: str) -> ProgramAnalysis:
    """Extract deterministic, explainable metrics for each top-level function."""
    tree = ast.parse(source)
    functions: dict[str, FunctionMetrics] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            visitor = _FunctionVisitor(node)
            visitor.visit(node)
            functions[node.name] = visitor.metrics()
    return ProgramAnalysis(functions)


def _reasons(before: FunctionMetrics, after: FunctionMetrics) -> Iterable[tuple[int, str]]:
    if after.max_loop_depth < before.max_loop_depth:
        yield 4, f"reduced maximum loop nesting from {before.max_loop_depth} to {after.max_loop_depth}"
    if after.repeated_sort_calls < before.repeated_sort_calls:
        yield 3, "moved or removed sorting from a loop"
    if after.list_membership_checks < before.list_membership_checks:
        yield 3, "removed linear list membership checks from a loop"
    if after.string_concat_in_loop < before.string_concat_in_loop:
        yield 2, "removed repeated string concatenation in a loop"
    if after.loop_count < before.loop_count:
        yield 2, f"reduced loop count from {before.loop_count} to {after.loop_count}"
    if after.cyclomatic_complexity < before.cyclomatic_complexity:
        yield 1, f"reduced cyclomatic complexity from {before.cyclomatic_complexity} to {after.cyclomatic_complexity}"


def analyze_versions(before_source: str, after_source: str) -> list[ChangeAttribution]:
    """Compare matching names and rank likely material improvements."""
    before_program = analyze_source(before_source)
    after_program = analyze_source(after_source)
    attributions: list[ChangeAttribution] = []
    for name in sorted(before_program.functions.keys() & after_program.functions.keys()):
        before, after = before_program.functions[name], after_program.functions[name]
        evidence = list(_reasons(before, after))
        if evidence:
            attributions.append(ChangeAttribution(name, sum(weight for weight, _ in evidence),
                                                  tuple(reason for _, reason in evidence), before, after))
    return sorted(attributions, key=lambda item: (-item.score, item.function))
