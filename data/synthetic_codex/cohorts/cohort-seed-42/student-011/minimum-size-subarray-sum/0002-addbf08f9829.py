def min_subarray_len(target, nums):
    start = 0
    running = 0
    answer = len(nums) + 1
    for end in range(len(nums)):
        running += nums[end]
        while running >= target:
            answer = min(answer, end - start + 1)
            running -= nums[start]
            start += 1
    return answer if answer <= len(nums) else 0
