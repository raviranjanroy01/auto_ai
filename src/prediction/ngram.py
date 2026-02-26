"""
N-Gram Language Model

Implements n-gram models (unigram, bigram, trigram) for
next-word prediction and language modeling.
"""

from collections import defaultdict, Counter


class NGramModel:
    """N-gram language model for next-word prediction."""

    def __init__(self, n: int = 3):
        """
        Initialize the N-Gram model.

        Args:
            n: The order of the n-gram model (default: trigram).
        """
        if n < 1:
            raise ValueError("n must be at least 1")

        self.n = n
        self.ngram_counts = defaultdict(Counter)
        self.context_totals = defaultdict(int)
        self.vocabulary = set()

    def train(self, text: str):
        """
        Train the model on a text corpus.

        Args:
            text: Training text (will be tokenized by whitespace).
        """
        tokens = text.lower().split()
        self.vocabulary.update(tokens)

        # Build n-grams for all orders from 1 to n
        for order in range(1, self.n + 1):
            for i in range(len(tokens) - order + 1):
                if order == 1:
                    # Unigram: context is empty
                    context = ()
                    word = tokens[i]
                else:
                    context = tuple(tokens[i:i + order - 1])
                    word = tokens[i + order - 1]

                self.ngram_counts[context][word] += 1
                self.context_totals[context] += 1

    def predict(self, context: str, top_k: int = 5) -> list:
        """
        Predict the next word given a context string.

        Args:
            context: The preceding text (last n-1 words are used).
            top_k: Number of top predictions to return.

        Returns:
            List of tuples (word, probability) sorted by probability.
        """
        tokens = context.lower().split()

        # Try from highest order n-gram down to unigram (backoff)
        for order in range(min(self.n, len(tokens) + 1), 0, -1):
            if order == 1:
                ctx = ()
            else:
                ctx = tuple(tokens[-(order - 1):])

            if ctx in self.ngram_counts and self.context_totals[ctx] > 0:
                total = self.context_totals[ctx]
                predictions = [
                    (word, count / total)
                    for word, count in self.ngram_counts[ctx].most_common(top_k)
                ]
                return predictions

        return []

    def probability(self, word: str, context: str) -> float:
        """
        Get the probability of a word given context.

        Args:
            word: The target word.
            context: The preceding text.

        Returns:
            The conditional probability P(word | context).
        """
        tokens = context.lower().split()
        word = word.lower()

        for order in range(min(self.n, len(tokens) + 1), 0, -1):
            if order == 1:
                ctx = ()
            else:
                ctx = tuple(tokens[-(order - 1):])

            if ctx in self.ngram_counts:
                total = self.context_totals[ctx]
                count = self.ngram_counts[ctx].get(word, 0)
                if total > 0:
                    return count / total

        return 0.0

    @property
    def vocab_size(self):
        """Return the vocabulary size."""
        return len(self.vocabulary)

    def __repr__(self):
        return f"NGramModel(n={self.n}, vocab_size={self.vocab_size})"
