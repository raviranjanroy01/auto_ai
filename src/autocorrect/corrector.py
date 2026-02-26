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
        return best[0]

    def get_candidates(self, word: str) -> list:
        """
        Generate correction candidates for a word.

        Args:
            word: The misspelled word.

        Returns:
            List of tuples (candidate_word, edit_distance).
        """
        candidates = []

        for dict_word in self.dictionary.get_words():
            distance = levenshtein_distance(word, dict_word)
            if distance <= self.max_edit_distance:
                candidates.append((dict_word, distance))

        return candidates

    def correct_text(self, text: str) -> str:
        """
        Correct all words in a text string.

        Args:
            text: The input text to correct.

        Returns:
            The corrected text.
        """
        words = text.split()
        corrected = [self.correct(word) for word in words]
        return " ".join(corrected)
