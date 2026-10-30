def rotate_array(nums, k):
    for _ in range(k):
        nums = [nums[-1]] + nums[:-1]
    return nums
# synthetic profile variant 204
