"""
User Learning Module

Processes user input to learn typing patterns, build
personal vocabulary, and improve prediction accuracy.
"""

from .profile import UserProfile
from prediction import NGramModel


class UserLearner:
    """Learns from user input to personalize the typing experience."""

    def __init__(self, profile: UserProfile = None):
        """
        Initialize the UserLearner.

        Args:
            profile: A UserProfile instance. Creates a default one if None.
        """
        self.profile = profile or UserProfile()
        self.personal_model = NGramModel(n=3)

    def learn_from_text(self, text: str):
        """
        Learn from a chunk of user-typed text.

        Args:
            text: The text the user typed.
        """
        words = text.lower().split()

        # Record individual words
        for word in words:
            self.profile.add_word(word)

        # Record word pairs
        for i in range(len(words) - 1):
            self.profile.add_word_pair(words[i], words[i + 1])

        # Train the personal n-gram model
        self.personal_model.train(text)

    def learn_correction(self, original: str, corrected: str):
        """
        Learn from a correction the user accepted.

        Args:
            original: The original (misspelled) word.
            corrected: The corrected word.
        """
        self.profile.add_correction(original, corrected)
        self.profile.add_word(corrected)

    def get_personal_predictions(self, context: str, top_k: int = 5) -> list:
        """
        Get predictions based on the user's personal model.

        Args:
            context: The preceding text.
            top_k: Number of predictions to return.

        Returns:
            List of (word, probability) tuples.
        """
        return self.personal_model.predict(context, top_k=top_k)

    def save(self, directory: str = "data/user_data"):
        """Save the user profile."""
        self.profile.save(directory)

    def __repr__(self):
        return f"UserLearner(profile={self.profile})"
