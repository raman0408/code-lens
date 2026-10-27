def min_subarray_len(target, nums):
    for value in nums:
        if value >= target:
            return 1
    return 0
