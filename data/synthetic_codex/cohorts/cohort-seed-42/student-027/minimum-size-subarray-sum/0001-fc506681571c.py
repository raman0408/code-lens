from bisect import bisect_left

def min_subarray_len(target, nums):
    prefix = [0]
    for value in nums:
        prefix.append(prefix[-1] + value)
    best = len(nums) + 1
    for start in range(len(nums)):
        end = bisect_left(prefix, prefix[start] + target, start + 1)
        if end <= len(nums):
            best = min(best, end - start)
    return 0 if best == len(nums) + 1 else best
