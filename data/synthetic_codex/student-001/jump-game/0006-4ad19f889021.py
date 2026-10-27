def can_jump(nums):
    furthest = 0
    for index, jump in enumerate(nums):
        if index > furthest:
            return False
        furthest = max(furthest, index + jump)
        if furthest >= len(nums) - 1:
            return True
    return True
