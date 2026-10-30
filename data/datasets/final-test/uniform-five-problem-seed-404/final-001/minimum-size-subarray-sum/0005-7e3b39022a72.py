def min_subarray_len(target, nums):
    best = len(nums) + 1
    left = total = 0
    for right, value in enumerate(nums):
        total += value
        while total >= target:
            best = min(best, right - left + 1)
            total -= nums[left]
            left += 1
    return best if best <= len(nums) else 0
# synthetic profile variant 405
