def is_palindrome(x):
    if x < 0:
        return False
    digits = str(x)
    return digits == digits[::-1]
