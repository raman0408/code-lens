def can_jump(nums):
    reachable = [False] * len(nums)
    reachable[0] = True
    for index in range(len(nums)):
        if reachable[index]:
            for step in range(1, nums[index] + 1):
                if index + step < len(nums):
                    reachable[index + step] = True
    return reachable[-1]
# synthetic profile variant 305
