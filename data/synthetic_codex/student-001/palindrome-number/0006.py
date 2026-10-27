def is_palindrome(x):
    if x < 0:
        return False
    digits = []
    for digit in str(x):
        digits.append(digit)
    return digits == digits[::-1]
