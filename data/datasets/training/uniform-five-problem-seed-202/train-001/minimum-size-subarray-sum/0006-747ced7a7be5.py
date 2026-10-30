def min_subarray_len(target, nums):
    left = total = 0
    best = float('inf')
    for right, value in enumerate(nums):
        total += value
        while total >= target:
            best = min(best, right - left + 1)
            total -= nums[left]
            left += 1
    return 0 if best == float('inf') else best
# synthetic profile variant 203
