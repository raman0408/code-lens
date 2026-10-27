def is_palindrome(x):
    digits = str(x)
    left = 0
    right = len(digits) - 1
    while left < right:
        if digits[left] != digits[right]:
            return False
        left += 1
        right -= 1
    return x >= 0
