def is_palindrome(x):
    if x < 0:
        return False
    original = x
    reversed_number = 0
    while x > 0:
        reversed_number = reversed_number * 10 + x % 10
        x //= 10
    return original == reversed_number
