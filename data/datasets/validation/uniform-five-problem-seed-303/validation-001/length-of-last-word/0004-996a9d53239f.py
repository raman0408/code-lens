def length_of_last_word(s):
    count = 0
    for char in reversed(s.rstrip()):
        if char == ' ':
            break
        count += 1
    return count
# synthetic profile variant 304
