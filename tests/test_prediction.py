"""Tests for the prediction engine."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from prediction import WordPredictor, NGramModel


class TestNGramModel:
    """Tests for the N-Gram model."""

    def test_train_and_predict(self):
        model = NGramModel(n=2)
        model.train("the cat sat on the mat")
        predictions = model.predict("the", top_k=3)
        assert len(predictions) > 0
        # "cat" and "mat" should both be predictions after "the"
        predicted_words = [w for w, _ in predictions]
        assert "cat" in predicted_words or "mat" in predicted_words

    def test_empty_predict(self):
        model = NGramModel(n=2)
        predictions = model.predict("hello", top_k=5)
        assert predictions == []

    def test_probability(self):
        model = NGramModel(n=2)
        model.train("hello world hello world hello world")
        prob = model.probability("world", "hello")
        assert prob > 0

    def test_vocab_size(self):
        model = NGramModel(n=2)
        model.train("one two three four five")
        assert model.vocab_size == 5


class TestWordPredictor:
    """Tests for the WordPredictor."""

    def test_untrained_returns_empty(self):
        predictor = WordPredictor()
        assert predictor.predict_next("hello") == []

    def test_trained_predicts(self):
        predictor = WordPredictor(n=2)
        predictor.train("I love coding and I love python")
        predictions = predictor.predict_next("I love", top_k=3)
        assert len(predictions) > 0

    def test_top_prediction(self):
        predictor = WordPredictor(n=2)
        predictor.train("hello world hello world hello world")
        top = predictor.get_top_prediction("hello")
        assert top == "world"

    def test_is_ready(self):
        predictor = WordPredictor()
        assert not predictor.is_ready
        predictor.train("some text")
        assert predictor.is_ready
