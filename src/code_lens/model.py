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
    sliding_window_patterns: int
    ast_node_count: int
    control_flow_node_count: int
    call_count: int
    return_count: int
    variable_read_count: int
    variable_write_count: int
    collection_allocation_count: int
    slice_count: int
    comprehension_count: int
    recursive_call_count: int


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
        self.sliding_window_patterns = 0
        # These are compiler-inspired, representation-level measurements. They
        # deliberately describe code shape instead of making another rule-based
        # verdict; downstream ML can learn how their changes interact.
        self.ast_node_count = 0
        self.control_flow_node_count = 0
        self.call_count = 0
        self.return_count = 0
        self.variable_read_count = 0
        self.variable_write_count = 0
        self.collection_allocation_count = 0
        self.slice_count = 0
        self.comprehension_count = 0
        self.recursive_call_count = 0
        self.string_names: set[str] = set()

    def generic_visit(self, node: ast.AST) -> None:
        self.ast_node_count += 1
        super().generic_visit(node)

    @staticmethod
    def _assigned_names(target: ast.AST) -> set[str]:
        if isinstance(target, ast.Name):
            return {target.id}
        if isinstance(target, (ast.Tuple, ast.List)):
            return set().union(*(_FunctionVisitor._assigned_names(item) for item in target.elts))
        return set()

    @staticmethod
    def _is_string_expression(node: ast.AST) -> bool:
        return isinstance(node, ast.JoinedStr) or (
            isinstance(node, ast.Constant) and isinstance(node.value, str)
        )

    def visit_Assign(self, node: ast.Assign) -> None:
        names = set().union(*(self._assigned_names(target) for target in node.targets))
        if self._is_string_expression(node.value):
            self.string_names.update(names)
        else:
            self.string_names.difference_update(names)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        names = self._assigned_names(node.target)
        if node.value is not None and self._is_string_expression(node.value):
            self.string_names.update(names)
        else:
            self.string_names.difference_update(names)
        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        self.complexity += 1
        self.control_flow_node_count += 1
        self.generic_visit(node)

    def visit_IfExp(self, node: ast.IfExp) -> None:
        self.complexity += 1
        self.control_flow_node_count += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        self.complexity += max(0, len(node.values) - 1)
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self.complexity += 1
        self.control_flow_node_count += 1
        self.generic_visit(node)

    def _visit_loop(self, node: ast.AST) -> None:
        self.complexity += 1
        self.control_flow_node_count += 1
        self.loop_count += 1
        self.loop_depth += 1
        self.max_loop_depth = max(self.max_loop_depth, self.loop_depth)
        self.generic_visit(node)
        self.loop_depth -= 1

    def visit_For(self, node: ast.For) -> None:
        if self._is_sliding_window(node):
            self.sliding_window_patterns += 1
        self._visit_loop(node)

    @staticmethod
    def _is_sliding_window(node: ast.For) -> bool:
        """Recognise a conservative expand/shrink window shape.

        The outer `for` expands a window; an inner `while` must test an ordered
        threshold and both shrink a running value and advance a boundary.
        """
        for child in node.body:
            if not isinstance(child, ast.While) or not _FunctionVisitor._has_threshold_test(child.test):
                continue
            additions = [item for item in ast.walk(child)
                         if isinstance(item, ast.AugAssign) and isinstance(item.target, ast.Name)
                         and isinstance(item.op, ast.Add) and isinstance(item.value, ast.Constant)
                         and isinstance(item.value.value, (int, float)) and item.value.value > 0]
            subtractions = [item for item in ast.walk(child)
                            if isinstance(item, ast.AugAssign) and isinstance(item.op, ast.Sub)]
            if additions and subtractions:
                return True
        return False

    @staticmethod
    def _has_threshold_test(node: ast.AST) -> bool:
        return any(isinstance(item, ast.Compare) and any(isinstance(op, (ast.Gt, ast.GtE)) for op in item.ops)
                   for item in ast.walk(node))

    def visit_While(self, node: ast.While) -> None:
        self._visit_loop(node)

    def visit_Call(self, node: ast.Call) -> None:
        self.call_count += 1
        if self.loop_depth and isinstance(node.func, ast.Attribute) and node.func.attr == "sort":
            self.repeated_sort_calls += 1
        if self.loop_depth and isinstance(node.func, ast.Name) and node.func.id == "sorted":
            self.repeated_sort_calls += 1
        if isinstance(node.func, ast.Name):
            if node.func.id == self.node.name:
                self.recursive_call_count += 1
            if node.func.id in {"list", "dict", "set"}:
                self.collection_allocation_count += 1
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        if self.loop_depth and any(isinstance(op, (ast.In, ast.NotIn)) for op in node.ops):
            if any(isinstance(value, (ast.List, ast.ListComp)) for value in node.comparators):
                self.list_membership_checks += 1
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        if (self.loop_depth and isinstance(node.op, ast.Add) and isinstance(node.target, ast.Name)
                and node.target.id in self.string_names):
            self.string_concat_in_loop += 1
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            self.variable_read_count += 1
        elif isinstance(node.ctx, (ast.Store, ast.Del)):
            self.variable_write_count += 1
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> None:
        self.return_count += 1
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        if isinstance(node.slice, ast.Slice):
            self.slice_count += 1
        self.generic_visit(node)

    def _visit_collection_literal(self, node: ast.AST, is_comprehension: bool = False) -> None:
        self.collection_allocation_count += 1
        self.comprehension_count += int(is_comprehension)
        self.generic_visit(node)

    def visit_List(self, node: ast.List) -> None:
        self._visit_collection_literal(node)

    def visit_Set(self, node: ast.Set) -> None:
        self._visit_collection_literal(node)

    def visit_Dict(self, node: ast.Dict) -> None:
        self._visit_collection_literal(node)

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._visit_collection_literal(node, is_comprehension=True)

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self._visit_collection_literal(node, is_comprehension=True)

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self._visit_collection_literal(node, is_comprehension=True)

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self.comprehension_count += 1
        self.generic_visit(node)

    def metrics(self) -> FunctionMetrics:
        return FunctionMetrics(self.node.name, self.node.lineno, self.complexity, self.loop_count,
                               self.max_loop_depth, self.repeated_sort_calls,
                               self.list_membership_checks, self.string_concat_in_loop,
                               self.sliding_window_patterns, self.ast_node_count,
                               self.control_flow_node_count, self.call_count, self.return_count,
                               self.variable_read_count, self.variable_write_count,
                               self.collection_allocation_count, self.slice_count,
                               self.comprehension_count, self.recursive_call_count)


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
    if after.sliding_window_patterns > before.sliding_window_patterns:
        yield 4, "introduced an expand/shrink sliding-window pattern"
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
