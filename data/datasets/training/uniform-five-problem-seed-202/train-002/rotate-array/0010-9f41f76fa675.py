def rotate_array(nums, k):
    k %= len(nums)
    return nums[-k:] + nums[:-k]
# synthetic profile variant 204
