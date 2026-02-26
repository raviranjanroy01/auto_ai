"""
Word Predictor

High-level interface for next-word prediction that combines
n-gram models with user personalization.
"""

from .ngram import NGramModel


class WordPredictor:
    """High-level next-word prediction engine."""

    def __init__(self, n: int = 3):
        """
        Initialize the WordPredictor.

        Args:
            n: Order of the underlying n-gram model.
        """
        self.model = NGramModel(n=n)
        self._is_trained = False

    def train(self, text: str):
        """
        Train the predictor on text data.

        Args:
            text: Training corpus text.
        """
        self.model.train(text)
        self._is_trained = True

    def predict_next(self, context: str, top_k: int = 5) -> list:
        """
        Predict the next word(s) given preceding text.

        Args:
            context: The text typed so far.
            top_k: Number of predictions to return.

        Returns:
            List of predicted words with probabilities.
        """
        if not self._is_trained:
            return []

        return self.model.predict(context, top_k=top_k)

    def get_top_prediction(self, context: str) -> str:
        """
        Get the single most likely next word.

        Args:
            context: The text typed so far.

        Returns:
            The predicted word, or empty string if no prediction.
        """
        predictions = self.predict_next(context, top_k=1)
        return predictions[0][0] if predictions else ""

    @property
    def is_ready(self) -> bool:
        """Check if the predictor has been trained."""
        return self._is_trained

    def __repr__(self):
        status = "trained" if self._is_trained else "untrained"
        return f"WordPredictor(status={status}, model={self.model})"
