def min_subarray_len(target, nums):
    best = len(nums) + 1
    for start in range(len(nums)):
        total = 0
        for end in range(start, len(nums)):
            total += nums[end]
            if total >= target:
                best = min(best, end - start + 1)
                break
    return 0 if best == len(nums) + 1 else best
# synthetic profile variant 205
