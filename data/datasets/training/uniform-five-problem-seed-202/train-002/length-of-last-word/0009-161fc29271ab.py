def length_of_last_word(s):
    count = 0
    for char in reversed(s):
        if char != ' ':
            count += 1
        elif count:
            return count
    return count
# synthetic profile variant 204
