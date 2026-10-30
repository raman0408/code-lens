def can_jump(nums):
    reachable = [False] * len(nums)
    reachable[0] = True
    for index, jump in enumerate(nums):
        if reachable[index]:
            for destination in range(index + 1, min(len(nums), index + jump + 1)):
                reachable[destination] = True
    return reachable[-1]
# synthetic profile variant 304
