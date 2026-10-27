def can_jump(nums):
    def visit(index):
        if index >= len(nums) - 1:
            return True
        return any(visit(index + step) for step in range(1, nums[index] + 1))
    return visit(0)
