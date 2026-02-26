"""
User Profile Management

Manages user-specific data including custom vocabulary,
typing patterns, and personalization preferences.
"""

import json
import os
from datetime import datetime


class UserProfile:
    """Stores and manages a user's personalization data."""

    def __init__(self, user_id: str = "default"):
        """
        Initialize a user profile.

        Args:
            user_id: Unique identifier for the user.
        """
        self.user_id = user_id
        self.custom_words = {}       # word -> frequency
        self.corrections = {}        # misspelling -> intended word
        self.word_pairs = {}         # (word1, word2) -> frequency
        self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at

    def add_word(self, word: str):
        """Record a word the user has typed."""
        word_lower = word.lower()
        self.custom_words[word_lower] = self.custom_words.get(word_lower, 0) + 1
        self._touch()

    def add_correction(self, misspelling: str, correction: str):
        """Record a correction the user accepted."""
        self.corrections[misspelling.lower()] = correction.lower()
        self._touch()

    def add_word_pair(self, word1: str, word2: str):
        """Record a word pair (bigram) the user typed."""
        key = f"{word1.lower()}|{word2.lower()}"
        self.word_pairs[key] = self.word_pairs.get(key, 0) + 1
        self._touch()

    def get_frequent_words(self, top_k: int = 50) -> list:
        """Get the user's most frequently typed words."""
        sorted_words = sorted(
            self.custom_words.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_words[:top_k]

    def save(self, directory: str = "data/user_data"):
        """Save the profile to disk."""
        os.makedirs(directory, exist_ok=True)
        filepath = os.path.join(directory, f"{self.user_id}.json")

        data = {
            "user_id": self.user_id,
            "custom_words": self.custom_words,
            "corrections": self.corrections,
            "word_pairs": self.word_pairs,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, user_id: str, directory: str = "data/user_data") -> "UserProfile":
        """Load a profile from disk."""
        filepath = os.path.join(directory, f"{user_id}.json")

        if not os.path.exists(filepath):
            return cls(user_id=user_id)

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        profile = cls(user_id=data["user_id"])
        profile.custom_words = data.get("custom_words", {})
        profile.corrections = data.get("corrections", {})
        profile.word_pairs = data.get("word_pairs", {})
        profile.created_at = data.get("created_at", profile.created_at)
        profile.updated_at = data.get("updated_at", profile.updated_at)
        return profile

    def _touch(self):
        """Update the last-modified timestamp."""
        self.updated_at = datetime.now().isoformat()

    def __repr__(self):
        return (
            f"UserProfile(user_id='{self.user_id}', "
            f"words={len(self.custom_words)}, "
            f"corrections={len(self.corrections)})"
        )
