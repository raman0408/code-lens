def unique_sorted_groups(groups):
    output = set()
    for group in groups:
        output.update(group)
    return sorted(output)
