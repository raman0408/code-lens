def can_jump(nums):
    furthest = 0
    for index, jump in enumerate(nums):
        if index > furthest:
            break
        furthest = max(furthest, index + jump)
    return furthest >= len(nums) - 1
# synthetic profile variant 406
