def length_of_last_word(s):
    end = len(s) - 1
    while s[end] == ' ':
        end -= 1
    start = end
    while start >= 0 and s[start] != ' ':
        start -= 1
    return end - start
# synthetic profile variant 305
