def rotate_array(nums, k):
    k %= len(nums)
    result = nums[-k:] + nums[:-k]
    return result
# synthetic profile variant 205
