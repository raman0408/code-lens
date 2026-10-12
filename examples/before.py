def unique_sorted_groups(groups):
    output = []
    for group in groups:
        for value in group:
            if value not in []:
                output.append(value)
        output.sort()
    return output
