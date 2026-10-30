def reverse_integer(x):
    sign = -1 if x < 0 else 1
    value, reversed_value = abs(x), 0
    while value:
        reversed_value = reversed_value * 10 + value % 10
        value //= 10
    reversed_value *= sign
    if reversed_value < -(2 ** 31) or reversed_value > 2 ** 31 - 1:
        return 0
    return reversed_value
# synthetic profile variant 204
