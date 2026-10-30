"""The fixed five-question catalogue used by the teacher-demo application."""

from __future__ import annotations

from dataclasses import dataclass

from code_lens.evaluation import ExerciseSpec


@dataclass(frozen=True)
class Problem:
    slug: str
    number: int
    title: str
    prompt: str
    starter_code: str
    spec: ExerciseSpec


def _spec(function_name: str, tests: tuple[tuple[list[object], object], ...],
          benchmark_args: tuple[list[object], ...] = ()) -> ExerciseSpec:
    return ExerciseSpec(function_name, tests, benchmark_args, benchmark_repeats=10)


PROBLEMS = (
    Problem("reverse-integer", 7, "Reverse Integer",
            "Return the reversed 32-bit signed integer, or 0 if it overflows.",
            "def reverse_integer(x):\n    # Write your solution here.\n    pass\n",
            _spec("reverse_integer", (([123], 321), ([-123], -321), ([120], 21), ([0], 0),
                                      ([1534236469], 0), ([-2147483412], -2143847412)),
                  ([123456789],))),
    Problem("jump-game", 55, "Jump Game",
            "Return whether the last index can be reached from the first index.",
            "def can_jump(nums):\n    # Write your solution here.\n    pass\n",
            _spec("can_jump", (([[2, 3, 1, 1, 4]], True), ([[3, 2, 1, 0, 4]], False),
                                ([[0]], True), ([[2, 0, 0]], True), ([[1, 0, 1]], False)),
                  ([[1] * 300],))),
    Problem("length-of-last-word", 58, "Length of Last Word",
            "Return the length of the final word in a string containing words and spaces.",
            "def length_of_last_word(s):\n    # Write your solution here.\n    pass\n",
            _spec("length_of_last_word", ((["Hello World"], 5), (["   fly me   to   the moon  "], 4),
                                           (["luffy is still joyboy"], 6), (["word"], 4), (["a  "], 1)),
                  (["word " * 500],))),
    Problem("rotate-array", 189, "Rotate Array",
            "Return the array rotated right by k positions. Return a new list; do not mutate the input.",
            "def rotate_array(nums, k):\n    # Write your solution here.\n    pass\n",
            _spec("rotate_array", (([[1, 2, 3, 4, 5, 6, 7], 3], [5, 6, 7, 1, 2, 3, 4]),
                                    ([[-1, -100, 3, 99], 2], [3, 99, -1, -100]),
                                    ([[1], 100], [1]), ([[1, 2], 0], [1, 2])),
                  ([list(range(200)), 100],))),
    Problem("minimum-size-subarray-sum", 209, "Minimum Size Subarray Sum",
            "Return the smallest length of a contiguous subarray with sum at least target, or 0.",
            "def min_subarray_len(target, nums):\n    # Write your solution here.\n    pass\n",
            _spec("min_subarray_len", (([7, [2, 3, 1, 2, 4, 3]], 2), ([4, [1, 4, 4]], 1),
                                        ([11, [1, 1, 1, 1, 1, 1, 1, 1]], 0),
                                        ([15, [5, 1, 3, 5, 10, 7, 4, 9, 2, 8]], 2)),
                  ([500, [1] * 500],))),
)

BY_SLUG = {problem.slug: problem for problem in PROBLEMS}
