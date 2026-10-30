def rotate_array(nums, k):
    k %= len(nums)
    for _ in range(k):
        nums.insert(0, nums.pop())
    return nums
# synthetic profile variant 205
