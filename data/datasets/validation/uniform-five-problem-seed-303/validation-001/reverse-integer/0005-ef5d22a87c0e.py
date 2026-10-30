def reverse_integer(x):
    sign = -1 if x < 0 else 1
    value = 0
    for digit in str(abs(x)):
        value = value * 10 + int(digit)
    value *= sign
    return value if -(2 ** 31) <= value <= 2 ** 31 - 1 else 0
# synthetic profile variant 304
