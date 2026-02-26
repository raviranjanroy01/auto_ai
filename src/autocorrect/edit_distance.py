"""
Edit Distance Algorithms

Implements Levenshtein distance and related string similarity
metrics used for spelling correction.
"""


def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Compute the Levenshtein (edit) distance between two strings.

    The Levenshtein distance is the minimum number of single-character
    edits (insertions, deletions, substitutions) required to transform
    one string into the other.

    Args:
        s1: First string.
        s2: Second string.

    Returns:
        The edit distance as an integer.
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)

    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            # Cost is 0 if characters match, 1 otherwise
            cost = 0 if c1 == c2 else 1
            current_row.append(min(
                current_row[j] + 1,       # Insertion
                previous_row[j + 1] + 1,  # Deletion
                previous_row[j] + cost     # Substitution
            ))
        previous_row = current_row

    return previous_row[-1]


def damerau_levenshtein_distance(s1: str, s2: str) -> int:
    """
    Compute the Damerau-Levenshtein distance between two strings.

    Like Levenshtein, but also allows transposition of two adjacent
    characters as a single edit operation.

    Args:
        s1: First string.
        s2: Second string.

    Returns:
        The edit distance as an integer.
    """
    len_s1 = len(s1)
    len_s2 = len(s2)

    # Create a matrix of size (len_s1+1) x (len_s2+1)
    d = [[0] * (len_s2 + 1) for _ in range(len_s1 + 1)]

    for i in range(len_s1 + 1):
        d[i][0] = i
    for j in range(len_s2 + 1):
        d[0][j] = j

    for i in range(1, len_s1 + 1):
        for j in range(1, len_s2 + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1

            d[i][j] = min(
                d[i - 1][j] + 1,       # Deletion
                d[i][j - 1] + 1,       # Insertion
                d[i - 1][j - 1] + cost  # Substitution
            )

            # Transposition
            if (i > 1 and j > 1
                    and s1[i - 1] == s2[j - 2]
                    and s1[i - 2] == s2[j - 1]):
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + cost)

    return d[len_s1][len_s2]
