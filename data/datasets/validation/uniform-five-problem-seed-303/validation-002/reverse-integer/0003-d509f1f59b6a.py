def reverse_integer(x):
    sign = -1 if x < 0 else 1
    return sign * int(str(abs(x))[::-1])
# synthetic profile variant 305
