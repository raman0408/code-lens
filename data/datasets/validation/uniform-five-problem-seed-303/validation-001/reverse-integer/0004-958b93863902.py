def reverse_integer(x):
    sign = -1 if x < 0 else 1
    value = sign * int(str(abs(x))[::-1])
    return value if -(2 ** 31) <= value <= 2 ** 31 - 1 else 0
# synthetic profile variant 304
