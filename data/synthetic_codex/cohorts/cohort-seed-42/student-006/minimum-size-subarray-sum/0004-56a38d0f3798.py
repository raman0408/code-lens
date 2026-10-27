def min_subarray_len(target, nums):
    candidates = []
    for start in range(len(nums)):
        total = 0
        for end in range(start, len(nums)):
            total += nums[end]
            if total >= target:
                candidates.append(end - start + 1)
                break
    return min(candidates) if candidates else 0
