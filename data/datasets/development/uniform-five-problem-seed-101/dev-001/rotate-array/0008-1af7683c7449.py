def rotate_array(nums, k):
    k %= len(nums)
    if k == 0:
        return nums
    return nums[-k:] + nums[:-k]
# synthetic profile variant 102
