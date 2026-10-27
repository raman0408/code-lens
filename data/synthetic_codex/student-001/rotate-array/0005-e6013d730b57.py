def rotate_array(nums, k):
    k %= len(nums)
    if not k:
        return nums
    return nums[-k:] + nums[:-k]
