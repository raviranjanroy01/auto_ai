"""
Dictionary / Vocabulary Management

Handles loading, storing, and querying the word dictionary
used for spell checking and correction candidates.
"""

import os
from collections import Counter


class Dictionary:
    """Manages the word dictionary for spell checking."""

    def __init__(self, words: dict = None):
        """
        Initialize the Dictionary.

        Args:
            words: Optional dict mapping words to their frequencies.
                   If None, a small default dictionary is used.
        """
        if words is not None:
            self._words = dict(words)
        else:
            self._words = self._default_dictionary()

    def _default_dictionary(self) -> dict:
        """Return a small built-in dictionary for testing."""
        common_words = [
            "the", "be", "to", "of", "and", "a", "in", "that", "have", "i",
            "it", "for", "not", "on", "with", "he", "as", "you", "do", "at",
            "this", "but", "his", "by", "from", "they", "we", "say", "her",
            "she", "or", "an", "will", "my", "one", "all", "would", "there",
            "their", "what", "so", "up", "out", "if", "about", "who", "get",
            "which", "go", "me", "when", "make", "can", "like", "time", "no",
            "just", "him", "know", "take", "people", "into", "year", "your",
            "good", "some", "could", "them", "see", "other", "than", "then",
            "now", "look", "only", "come", "its", "over", "think", "also",
            "back", "after", "use", "two", "how", "our", "work", "first",
            "well", "way", "even", "new", "want", "because", "any", "these",
            "give", "day", "most", "us", "hello", "world", "python",
            "computer", "program", "code", "data", "system", "model",
            "learning", "machine", "artificial", "intelligence", "typing",
            "assistant", "keyboard", "prediction", "correction", "word",
            "text", "language", "input", "output", "user", "interface",
        ]
        # Assign decreasing frequencies so common words rank higher
        return {word: max(1, 120 - i) for i, word in enumerate(common_words)}

    def contains(self, word: str) -> bool:
        """Check if a word exists in the dictionary."""
        return word.lower() in self._words

    def get_frequency(self, word: str) -> int:
        """Get the frequency count of a word. Returns 0 if not found."""
        return self._words.get(word.lower(), 0)

    def get_words(self) -> list:
        """Return all words in the dictionary."""
        return list(self._words.keys())

    def add_word(self, word: str, frequency: int = 1):
        """Add a word or increase its frequency."""
        word_lower = word.lower()
        self._words[word_lower] = self._words.get(word_lower, 0) + frequency

    def load_from_file(self, filepath: str):
        """
        Load words from a text file (one word per line).

        Args:
            filepath: Path to the dictionary file.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Dictionary file not found: {filepath}")

        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) == 2:
                    word, freq = parts[0], int(parts[1])
                    self._words[word] = freq
                elif len(parts) == 1:
                    # Fallback for old single-word format
                    self._words[parts[0]] = self._words.get(parts[0], 0) + 1

    def save_to_file(self, filepath: str):
        """
        Save the dictionary to a file.

        Args:
            filepath: Path to save the dictionary to.
        """
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            for word, freq in sorted(self._words.items()):
                f.write(f"{word} {freq}\n")

    def __len__(self):
        return len(self._words)

    def __repr__(self):
        return f"Dictionary(size={len(self)})"
