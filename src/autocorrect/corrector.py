"""
Auto-Correction Engine

Provides context-aware spelling correction by combining
edit distance algorithms with dictionary lookup and
optional language model scoring.
"""

from .edit_distance import levenshtein_distance
from .dictionary import Dictionary


class AutoCorrector:
    """Main auto-correction engine."""

    def __init__(self, dictionary: Dictionary = None, max_edit_distance: int = 2):
        """
        Initialize the AutoCorrector.

        Args:
            dictionary: A Dictionary instance for word lookup.
            max_edit_distance: Maximum edit distance to consider for corrections.
        """
        self.dictionary = dictionary or Dictionary()
        self.max_edit_distance = max_edit_distance

    def correct(self, word: str) -> str:
        """
        Correct a single word.

        Args:
            word: The word to correct.

        Returns:
            The corrected word, or the original word if no correction is needed.
        """
        if not word:
            return ""

        word_lower = word.lower()

        # If the word is already in the dictionary, return it as-is
        if self.dictionary.contains(word_lower):
            return word

        # Find candidates within max edit distance
        candidates = self.get_candidates(word_lower)

        if not candidates:
            return word

        # Return the candidate with the smallest edit distance,
        # breaking ties by word frequency
        best = min(
            candidates,
            key=lambda c: (c[1], -self.dictionary.get_frequency(c[0]))
        )
        
        # Preserve original casing if possible
        corrected = best[0]
        if word.isupper():
            return corrected.upper()
        if word[0].isupper():
            return corrected.capitalize()
        return corrected

    def get_candidates(self, word: str) -> list:
        """
        Generate correction candidates for a word using a fast lookup strategy.
        Generates edits of distance 1 and 2 and checks if they exist in the dictionary.
        """
        # Distance 0:
        if self.dictionary.contains(word):
            return [(word, 0)]

        # Distance 1:
        edits1 = self._get_edits1(word)
        candidates1 = [(w, 1) for w in edits1 if self.dictionary.contains(w)]
        if candidates1:
            return candidates1

        # Distance 2:
        if self.max_edit_distance >= 2:
            candidates2 = []
            for e1 in edits1:
                edits2 = self._get_edits1(e1)
                candidates2.extend([(w, 2) for w in edits2 if self.dictionary.contains(w)])
            if candidates2:
                # Return only unique candidates to avoid redundant lookups
                return list(set(candidates2))

        return []

    def _get_edits1(self, word: str) -> set:
        """Generate all strings that are one edit away from 'word'."""
        letters = 'abcdefghijklmnopqrstuvwxyz'
        splits = [(word[:i], word[i:]) for i in range(len(word) + 1)]
        deletes = [L + R[1:] for L, R in splits if R]
        transposes = [L + R[1] + R[0] + R[2:] for L, R in splits if len(R) > 1]
        replaces = [L + c + R[1:] for L, R in splits if R for c in letters]
        inserts = [L + c + R for L, R in splits for c in letters]
        return set(deletes + transposes + replaces + inserts)

    def correct_text(self, text: str) -> str:
        """
        Correct all words in a text string, preserving punctuation and formatting.
        """
        import re
        # Find all words and separators
        tokens = re.split(r'(\W+)', text)
        corrected = []
        for token in tokens:
            # If it's a word (contains alphanumeric), correct it
            if re.match(r'\w+', token):
                corrected.append(self.correct(token))
            else:
                corrected.append(token)
        return "".join(corrected)
