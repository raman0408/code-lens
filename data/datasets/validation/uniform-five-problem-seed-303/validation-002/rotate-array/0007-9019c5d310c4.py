def rotate_array(nums, k):
    k %= len(nums)
    return nums[len(nums) - k:] + nums[:len(nums) - k]
# synthetic profile variant 305
