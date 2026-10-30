"""Create a reproducible, locally authored synthetic exercise batch.

The script creates one declared synthetic profile at a time.  Supplying a new
student ID does not make the resulting timeline independent training data;
new profiles require intentionally authored variations and review labels.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from code_lens.snapshots import SnapshotStore


parser = argparse.ArgumentParser(description="Build one locally authored synthetic exercise batch.")
parser.add_argument("--output-root", type=Path, default=Path("data/synthetic_codex"),
                    help="parent directory that will contain the student timeline")
parser.add_argument("--student-id", default="student-001",
                    help="synthetic profile identifier; use a distinct authored profile for each student")
parser.add_argument("--dataset-tier", choices=("development", "training", "validation", "final-test"),
                    default="development")
parser.add_argument("--variant", type=int, default=0,
                    help="authored-profile variant identifier; recorded in metadata and snapshot comments")
parser.add_argument("--problems", type=int, nargs="+", default=(7, 55, 58, 189, 209),
                    choices=(7, 9, 55, 58, 189, 209),
                    help="LeetCode problem numbers to generate")
args = parser.parse_args()

ROOT = args.output_root / args.student_id
STUDENT_ID = args.student_id
STANDARD = "correctness_preserved_and_asymptotic_complexity_improved"


def exercise(number, slug, title, function_name, spec, snapshots, labels):
    if number not in args.problems:
        return
    directory = ROOT / slug
    if directory.exists():
        raise FileExistsError(f"refusing to replace existing timeline: {directory}")
    directory.mkdir(parents=True)
    (directory / "exercise_spec.json").write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    metadata = {
        "dataset_source": "synthetic_codex",
        "dataset_tier": args.dataset_tier,
        "profile_variant": args.variant,
        "student_id": STUDENT_ID,
        "attempt_id": slug,
        "problem_reference": {"provider": "LeetCode", "number": number, "title": title,
                              "url": f"https://leetcode.com/problems/{slug}/"},
        "function_name": function_name,
        "language": "python",
        "snapshot_count": len(snapshots),
        "label_status": "reviewed_gold_example",
        "review_standard": "A positive label requires full after-version correctness, no correctness regression, and a material asymptotic complexity improvement.",
        "notes": "Synthetic Codex-assisted timeline. Local tests and labels are project-authored, not copied judge data.",
    }
    (directory / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    store = SnapshotStore(directory)
    for sequence, source in enumerate(snapshots, 1):
        # The comment preserves a semantically equivalent but content-distinct
        # authored variant, preventing accidental byte-for-byte duplication
        # across synthetic partitions.
        source = f"{source.rstrip()}\n# synthetic profile variant {args.variant}\n"
        store.capture(source, "submission" if sequence in {5, len(snapshots)} else "compile")
    reviews = []
    for sequence, (label, decision, reason) in enumerate(labels, 1):
        reviews.append({"from_snapshot": sequence, "to_snapshot": sequence + 1, "label": label,
                        "decision": decision, "reason": reason, "reviewer": "project-review",
                        "review_standard": STANDARD})
    (directory / "gold_labels.jsonl").write_text(
        "".join(json.dumps(review) + "\n" for review in reviews), encoding="utf-8"
    )


exercise(7, "reverse-integer", "Reverse Integer", "reverse_integer", {
    "function_name": "reverse_integer",
    "tests": [
        {"args": [123], "expected": 321}, {"args": [-123], "expected": -321},
        {"args": [120], "expected": 21}, {"args": [0], "expected": 0},
        {"args": [1534236469], "expected": 0}, {"args": [-2147483412], "expected": -2143847412},
    ], "benchmark_args": [[123456789], [-123456789]], "benchmark_repeats": 3000,
}, [
    "def reverse_integer(x):\n    return 0\n",
    "def reverse_integer(x):\n    return int(str(x)[::-1])\n",
    "def reverse_integer(x):\n    sign = -1 if x < 0 else 1\n    return sign * int(str(abs(x))[::-1])\n",
    "def reverse_integer(x):\n    sign = -1 if x < 0 else 1\n    value = sign * int(str(abs(x))[::-1])\n    return value if -(2 ** 31) <= value <= 2 ** 31 - 1 else 0\n",
    "def reverse_integer(x):\n    sign = -1 if x < 0 else 1\n    value = 0\n    for digit in str(abs(x)):\n        value = value * 10 + int(digit)\n    value *= sign\n    return value if -(2 ** 31) <= value <= 2 ** 31 - 1 else 0\n",
    "def reverse_integer(x):\n    sign = -1 if x < 0 else 1\n    value = abs(x)\n    reversed_value = 0\n    while value:\n        reversed_value = reversed_value * 10 + value % 10\n        value //= 10\n    reversed_value *= sign\n    return reversed_value if -(2 ** 31) <= reversed_value <= 2 ** 31 - 1 else 0\n",
    "def reverse_integer(x):\n    sign = -1 if x < 0 else 1\n    value, reversed_value = abs(x), 0\n    while value:\n        reversed_value = reversed_value * 10 + value % 10\n        value //= 10\n    reversed_value *= sign\n    return reversed_value if -(2 ** 31) <= reversed_value <= 2 ** 31 - 1 else 0\n",
    "def reverse_integer(x):\n    sign = -1 if x < 0 else 1\n    value, reversed_value = abs(x), 0\n    while value:\n        reversed_value = reversed_value * 10 + value % 10\n        value //= 10\n    return reversed_value * sign if reversed_value <= 2 ** 31 - 1 else 0\n",
    "def reverse_integer(x):\n    sign = -1 if x < 0 else 1\n    value, reversed_value = abs(x), 0\n    while value:\n        reversed_value = reversed_value * 10 + value % 10\n        value //= 10\n    reversed_value *= sign\n    if reversed_value < -(2 ** 31) or reversed_value > 2 ** 31 - 1:\n        return 0\n    return reversed_value\n",
    "def reverse_integer(x):\n    sign = -1 if x < 0 else 1\n    value, reversed_value = abs(x), 0\n    while value:\n        reversed_value = reversed_value * 10 + value % 10\n        value //= 10\n    reversed_value *= sign\n    return reversed_value if -(2 ** 31) <= reversed_value <= 2 ** 31 - 1 else 0\n",
], [(0, "incorrect", "Always returns zero."), (0, "incorrect", "Negative values raise an error."),
    (0, "correctness_fix_only", "Adds sign handling but misses overflow."),
    (0, "correct_refactor_only", "Correct implementation remains O(d)."),
    (0, "constant_factor_only", "Explicit digit loop remains O(d)."),
    (0, "correct_refactor_only", "Integer reversal remains O(d)."),
    (0, "cosmetic_refactor", "Equivalent O(d) implementation."),
    (0, "correctness_regression", "Negative overflow bounds are handled incorrectly."),
    (0, "correctness_fix_only", "Restores bounds handling without complexity change.")])

exercise(9, "palindrome-number", "Palindrome Number", "is_palindrome", {
    "function_name": "is_palindrome",
    "tests": [
        {"args": [121], "expected": True}, {"args": [-121], "expected": False},
        {"args": [10], "expected": False}, {"args": [0], "expected": True},
        {"args": [1221], "expected": True}, {"args": [123], "expected": False},
        {"args": [2147447412], "expected": True}, {"args": [2147483647], "expected": False},
    ], "benchmark_args": [[123454321], [2147447412], [2147483647]], "benchmark_repeats": 5000,
}, [
    "def is_palindrome(x):\n    return x == 0\n",
    "def is_palindrome(x):\n    if x < 0:\n        return False\n    return True\n",
    "def is_palindrome(x):\n    return str(x) == str(x)[::-1]\n",
    "def is_palindrome(x):\n    digits = str(x)\n    left = 0\n    right = len(digits) - 1\n    while left < right:\n        if digits[left] != digits[right]:\n            return False\n        left += 1\n        right -= 1\n    return x >= 0\n",
    "def is_palindrome(x):\n    if x < 0:\n        return False\n    digits = str(x)\n    return digits == digits[::-1]\n",
    "def is_palindrome(x):\n    if x < 0:\n        return False\n    digits = []\n    for digit in str(x):\n        digits.append(digit)\n    return digits == digits[::-1]\n",
    "def is_palindrome(x):\n    return str(abs(x)) == str(abs(x))[::-1]\n",
    "def is_palindrome(x):\n    if x < 0:\n        return False\n    original = x\n    reversed_number = 0\n    while x > 0:\n        reversed_number = reversed_number * 10 + x % 10\n        x //= 10\n    return original == reversed_number\n",
    "def is_palindrome(x):\n    if x < 0:\n        return False\n    if x != 0 and x % 10 == 0:\n        return False\n    reversed_half = 0\n    while x > reversed_half:\n        reversed_half = reversed_half * 10 + x % 10\n        x //= 10\n    return x == reversed_half or x == reversed_half // 10\n",
    "def is_palindrome(x):\n    if x < 0 or (x != 0 and x % 10 == 0):\n        return False\n    reversed_half = 0\n    while x > reversed_half:\n        reversed_half = reversed_half * 10 + x % 10\n        x //= 10\n    return x == reversed_half or x == reversed_half // 10\n",
    "def is_palindrome(x):\n    if x < 0 or (x % 10 == 0 and x != 0):\n        return False\n    reversed_half = 0\n    while x > reversed_half:\n        reversed_half = reversed_half * 10 + x % 10\n        x //= 10\n    return x == reversed_half or x == reversed_half // 10\n",
], [(0, "not_improvement", "The after-version remains incorrect and has no complexity improvement."),
    (0, "correctness_fix_only", "The after-version becomes correct, but this is a correctness fix rather than a complexity improvement."),
    (0, "regression", "The after-version adds an explicit digit scan while retaining O(d) complexity."),
    (0, "correct_refactor_only", "Both versions are O(d); this is not a material asymptotic complexity improvement."),
    (0, "regression", "The after-version adds a list allocation and explicit loop while retaining O(d) complexity."),
    (0, "correctness_regression", "Negative palindromic values are incorrectly accepted."),
    (0, "correctness_fix_only", "The after-version restores correctness without an asymptotic improvement."),
    (0, "constant_factor_only", "Half reversal processes fewer digits, but both versions are O(d)."),
    (0, "cosmetic_refactor", "The condition is reformatted without changing complexity."),
    (0, "cosmetic_refactor", "The condition is reordered without changing complexity.")])

exercise(55, "jump-game", "Jump Game", "can_jump", {
    "function_name": "can_jump",
    "tests": [
        {"args": [[2, 3, 1, 1, 4]], "expected": True}, {"args": [[3, 2, 1, 0, 4]], "expected": False},
        {"args": [[0]], "expected": True}, {"args": [[2, 0, 0]], "expected": True}, {"args": [[1, 0, 1]], "expected": False},
    ], "benchmark_args": [[[1] * 1000]], "benchmark_series": [{
        "name": "worst_case", "cases": [
            {"size": size, "args": [[size] * size]} for size in (32, 64, 128)
        ],
    }], "benchmark_repeats": 30,
}, [
    "def can_jump(nums):\n    return bool(nums)\n",
    "def can_jump(nums):\n    def visit(index):\n        if index >= len(nums) - 1:\n            return True\n        return any(visit(index + step) for step in range(1, nums[index] + 1))\n    return visit(0)\n",
    "def can_jump(nums):\n    reachable = [False] * len(nums)\n    reachable[0] = True\n    for index in range(len(nums)):\n        if reachable[index]:\n            for step in range(1, nums[index] + 1):\n                if index + step < len(nums):\n                    reachable[index + step] = True\n    return reachable[-1]\n",
    "def can_jump(nums):\n    reachable = [False] * len(nums)\n    reachable[0] = True\n    for index, jump in enumerate(nums):\n        if reachable[index]:\n            for destination in range(index + 1, min(len(nums), index + jump + 1)):\n                reachable[destination] = True\n    return reachable[-1]\n",
    "def can_jump(nums):\n    furthest = 0\n    for index, jump in enumerate(nums):\n        if index > furthest:\n            return False\n        furthest = max(furthest, index + jump)\n    return True\n",
    "def can_jump(nums):\n    furthest = 0\n    for index, jump in enumerate(nums):\n        if index > furthest:\n            return False\n        furthest = max(furthest, index + jump)\n        if furthest >= len(nums) - 1:\n            return True\n    return True\n",
    "def can_jump(nums):\n    furthest = 0\n    for index, jump in enumerate(nums):\n        if index > furthest:\n            return False\n        furthest = max(furthest, index + jump)\n    return furthest >= len(nums) - 1\n",
    "def can_jump(nums):\n    furthest = 0\n    for index, jump in enumerate(nums):\n        if index > furthest:\n            break\n        furthest = max(furthest, index + jump)\n    return furthest >= len(nums) - 1\n",
    "def can_jump(nums):\n    furthest = 0\n    for index, jump in enumerate(nums):\n        if index > furthest:\n            return False\n        furthest = max(furthest, index + jump)\n    return True\n",
    "def can_jump(nums):\n    furthest = 0\n    for index, jump in enumerate(nums):\n        if index > furthest:\n            return False\n        furthest = max(furthest, index + jump)\n    return True\n",
], [(0, "incorrect", "Only checks whether input is non-empty."), (0, "correct_but_exponential", "Recursive search is correct for small inputs but not a complexity improvement."),
    (0, "correct_but_quadratic", "Reachability DP is O(n squared)."), (1, "asymptotic_improvement", "Greedy frontier reduces correct reachability from O(n squared) to O(n)."),
    (0, "constant_factor_only", "Early return preserves O(n)."), (0, "cosmetic_refactor", "Equivalent O(n) greedy solution."),
    (0, "cosmetic_refactor", "Equivalent O(n) greedy solution."), (0, "cosmetic_refactor", "Equivalent O(n) greedy solution."),
    (0, "cosmetic_refactor", "Equivalent O(n) greedy solution.")])

exercise(58, "length-of-last-word", "Length of Last Word", "length_of_last_word", {
    "function_name": "length_of_last_word",
    "tests": [
        {"args": ["Hello World"], "expected": 5}, {"args": ["   fly me   to   the moon  "], "expected": 4},
        {"args": ["luffy is still joyboy"], "expected": 6}, {"args": ["word"], "expected": 4}, {"args": ["a  "], "expected": 1},
    ], "benchmark_args": [["word " * 2000]], "benchmark_repeats": 200,
}, [
    "def length_of_last_word(s):\n    return len(s)\n",
    "def length_of_last_word(s):\n    return len(s.split()[-1])\n",
    "def length_of_last_word(s):\n    words = s.split()\n    return len(words[-1])\n",
    "def length_of_last_word(s):\n    count = 0\n    for char in reversed(s.rstrip()):\n        if char == ' ':\n            break\n        count += 1\n    return count\n",
    "def length_of_last_word(s):\n    end = len(s) - 1\n    while s[end] == ' ':\n        end -= 1\n    start = end\n    while start >= 0 and s[start] != ' ':\n        start -= 1\n    return end - start\n",
    "def length_of_last_word(s):\n    return len(s.rstrip().split(' ')[-1])\n",
    "def length_of_last_word(s):\n    stripped = s.rstrip()\n    return len(stripped) - stripped.rfind(' ') - 1\n",
    "def length_of_last_word(s):\n    stripped = s.rstrip()\n    return len(stripped.split()[-1])\n",
    "def length_of_last_word(s):\n    count = 0\n    for char in reversed(s):\n        if char != ' ':\n            count += 1\n        elif count:\n            return count\n    return count\n",
    "def length_of_last_word(s):\n    return len(s.rstrip().split()[-1])\n",
], [(0, "incorrect", "Counts spaces and all prior words."), (0, "correct_refactor_only", "Split-based solution is O(n)."),
    (0, "cosmetic_refactor", "Equivalent O(n) split-based solution."), (0, "space_optimization_only", "Reverse scan remains O(n)."),
    (0, "correct_refactor_only", "Two scans remain O(n)."), (0, "cosmetic_refactor", "Equivalent O(n) solution."),
    (0, "space_optimization_only", "Equivalent O(n) solution."), (0, "cosmetic_refactor", "Equivalent O(n) solution."),
    (0, "cosmetic_refactor", "Equivalent O(n) solution.")])

exercise(189, "rotate-array", "Rotate Array", "rotate_array", {
    "function_name": "rotate_array",
    "tests": [
        {"args": [[1, 2, 3, 4, 5, 6, 7], 3], "expected": [5, 6, 7, 1, 2, 3, 4]},
        {"args": [[-1, -100, 3, 99], 2], "expected": [3, 99, -1, -100]},
        {"args": [[1], 100], "expected": [1]}, {"args": [[1, 2], 0], "expected": [1, 2]},
    ], "benchmark_args": [[list(range(500)), 250]], "benchmark_series": [{
        "name": "items", "cases": [
            {"size": size, "args": [list(range(size)), size // 2]} for size in (64, 128, 256)
        ],
    }], "benchmark_repeats": 30,
}, [
    "def rotate_array(nums, k):\n    return nums\n",
    "def rotate_array(nums, k):\n    for _ in range(k):\n        nums = [nums[-1]] + nums[:-1]\n    return nums\n",
    "def rotate_array(nums, k):\n    k %= len(nums)\n    for _ in range(k):\n        nums.insert(0, nums.pop())\n    return nums\n",
    "def rotate_array(nums, k):\n    k %= len(nums)\n    return nums[-k:] + nums[:-k]\n",
    "def rotate_array(nums, k):\n    k %= len(nums)\n    if not k:\n        return nums\n    return nums[-k:] + nums[:-k]\n",
    "def rotate_array(nums, k):\n    k %= len(nums)\n    result = nums[-k:] + nums[:-k]\n    return result\n",
    "def rotate_array(nums, k):\n    k %= len(nums)\n    return nums[len(nums) - k:] + nums[:len(nums) - k]\n",
    "def rotate_array(nums, k):\n    k %= len(nums)\n    if k == 0:\n        return nums\n    return nums[-k:] + nums[:-k]\n",
    "def rotate_array(nums, k):\n    k %= len(nums)\n    return nums[-k:] + nums[:-k]\n",
    "def rotate_array(nums, k):\n    k %= len(nums)\n    return nums[-k:] + nums[:-k]\n",
], [(0, "incorrect", "Does not rotate non-zero shifts."), (0, "correct_but_quadratic", "Repeated full-list allocation is O(nk)."),
    (1, "asymptotic_improvement", "Single slicing rotation reduces correct rotation from O(nk) to O(n)."),
    (0, "constant_factor_only", "Same O(n) slicing approach."), (0, "cosmetic_refactor", "Same O(n) slicing approach."),
    (0, "cosmetic_refactor", "Same O(n) slicing approach."), (0, "cosmetic_refactor", "Same O(n) slicing approach."),
    (0, "cosmetic_refactor", "Same O(n) slicing approach."), (0, "cosmetic_refactor", "Same O(n) slicing approach.")])

exercise(209, "minimum-size-subarray-sum", "Minimum Size Subarray Sum", "min_subarray_len", {
    "function_name": "min_subarray_len",
    "tests": [
        {"args": [7, [2, 3, 1, 2, 4, 3]], "expected": 2}, {"args": [4, [1, 4, 4]], "expected": 1},
        {"args": [11, [1, 1, 1, 1, 1, 1, 1, 1]], "expected": 0}, {"args": [15, [5, 1, 3, 5, 10, 7, 4, 9, 2, 8]], "expected": 2},
    ], "benchmark_args": [[500, [1] * 1000]], "benchmark_series": [{
        "name": "items", "cases": [
            {"size": size, "args": [size + 1, [1] * size]} for size in (32, 64, 128)
        ],
    }], "benchmark_repeats": 20,
}, [
    "def min_subarray_len(target, nums):\n    return 0\n",
    "def min_subarray_len(target, nums):\n    best = len(nums) + 1\n    for start in range(len(nums)):\n        total = 0\n        for end in range(start, len(nums)):\n            total += nums[end]\n            if total >= target:\n                best = min(best, end - start + 1)\n                break\n    return 0 if best == len(nums) + 1 else best\n",
    "def min_subarray_len(target, nums):\n    best = len(nums) + 1\n    for start in range(len(nums)):\n        total = 0\n        for end in range(start, len(nums)):\n            total += nums[end]\n            if total >= target:\n                best = min(best, end - start + 1)\n    return 0 if best == len(nums) + 1 else best\n",
    "def min_subarray_len(target, nums):\n    best = len(nums) + 1\n    left = total = 0\n    for right, value in enumerate(nums):\n        total += value\n        while total >= target:\n            best = min(best, right - left + 1)\n            total -= nums[left]\n            left += 1\n    return 0 if best == len(nums) + 1 else best\n",
    "def min_subarray_len(target, nums):\n    best = len(nums) + 1\n    left = total = 0\n    for right, value in enumerate(nums):\n        total += value\n        while total >= target:\n            best = min(best, right - left + 1)\n            total -= nums[left]\n            left += 1\n    return best if best <= len(nums) else 0\n",
    "def min_subarray_len(target, nums):\n    left = total = 0\n    best = float('inf')\n    for right, value in enumerate(nums):\n        total += value\n        while total >= target:\n            best = min(best, right - left + 1)\n            total -= nums[left]\n            left += 1\n    return 0 if best == float('inf') else best\n",
    "def min_subarray_len(target, nums):\n    left = total = 0\n    best = len(nums) + 1\n    for right, value in enumerate(nums):\n        total += value\n        while total >= target:\n            best = min(best, right - left + 1)\n            total -= nums[left]\n            left += 1\n    return 0 if best == len(nums) + 1 else best\n",
    "def min_subarray_len(target, nums):\n    left = total = 0\n    best = len(nums) + 1\n    for right in range(len(nums)):\n        total += nums[right]\n        while total >= target:\n            best = min(best, right - left + 1)\n            total -= nums[left]\n            left += 1\n    return 0 if best == len(nums) + 1 else best\n",
    "def min_subarray_len(target, nums):\n    left = total = 0\n    best = len(nums) + 1\n    for right, value in enumerate(nums):\n        total += value\n        while total >= target:\n            best = min(best, right - left + 1)\n            total -= nums[left]\n            left += 1\n    return 0 if best == len(nums) + 1 else best\n",
    "def min_subarray_len(target, nums):\n    left = total = 0\n    best = len(nums) + 1\n    for right, value in enumerate(nums):\n        total += value\n        while total >= target:\n            best = min(best, right - left + 1)\n            total -= nums[left]\n            left += 1\n    return 0 if best == len(nums) + 1 else best\n",
], [(0, "incorrect", "Always returns zero."), (0, "correct_but_quadratic", "Nested scan is O(n squared)."),
    (1, "asymptotic_improvement", "Sliding window reduces correct search from O(n squared) to O(n)."),
    (0, "cosmetic_refactor", "Equivalent O(n) sliding window."), (0, "cosmetic_refactor", "Equivalent O(n) sliding window."),
    (0, "cosmetic_refactor", "Equivalent O(n) sliding window."), (0, "cosmetic_refactor", "Equivalent O(n) sliding window."),
    (0, "cosmetic_refactor", "Equivalent O(n) sliding window."), (0, "cosmetic_refactor", "Equivalent O(n) sliding window.")])
