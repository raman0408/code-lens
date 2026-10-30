def length_of_last_word(s):
    stripped = s.rstrip()
    return len(stripped) - stripped.rfind(' ') - 1
# synthetic profile variant 205
