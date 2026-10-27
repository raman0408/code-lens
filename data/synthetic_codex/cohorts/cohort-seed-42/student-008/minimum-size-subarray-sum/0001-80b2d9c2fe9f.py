def min_subarray_len(target, nums):
    answer = len(nums) + 1
    for left in range(len(nums)):
        running = 0
        for right in range(left, len(nums)):
            running += nums[right]
            if running >= target:
                answer = min(answer, right - left + 1)
    return answer if answer <= len(nums) else 0
