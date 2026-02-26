"""Tests for the auto-correction engine."""

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from autocorrect import AutoCorrector, Dictionary, levenshtein_distance


class TestEditDistance:
    """Tests for edit distance algorithms."""

    def test_identical_strings(self):
        assert levenshtein_distance("hello", "hello") == 0

    def test_single_insertion(self):
        assert levenshtein_distance("hell", "hello") == 1

    def test_single_deletion(self):
        assert levenshtein_distance("hello", "hell") == 1

    def test_single_substitution(self):
        assert levenshtein_distance("hello", "hallo") == 1

    def test_empty_string(self):
        assert levenshtein_distance("", "hello") == 5
        assert levenshtein_distance("hello", "") == 5

    def test_both_empty(self):
        assert levenshtein_distance("", "") == 0


class TestDictionary:
    """Tests for Dictionary class."""

    def test_default_dictionary(self):
        d = Dictionary()
        assert len(d) > 0
        assert d.contains("the")
        assert d.contains("hello")

    def test_custom_words(self):
        d = Dictionary({"foo": 10, "bar": 5})
        assert d.contains("foo")
        assert d.contains("bar")
        assert not d.contains("baz")

    def test_add_word(self):
        d = Dictionary({"existing": 1})
        d.add_word("newword")
        assert d.contains("newword")

    def test_frequency(self):
        d = Dictionary({"hello": 100})
        assert d.get_frequency("hello") == 100
        assert d.get_frequency("missing") == 0


class TestAutoCorrector:
    """Tests for the AutoCorrector."""

    def test_correct_word_unchanged(self):
        corrector = AutoCorrector()
        result = corrector.correct("hello")
        assert result == "hello"

    def test_simple_correction(self):
        corrector = AutoCorrector()
        result = corrector.correct("helo")
        assert result == "hello"

    def test_correct_text(self):
        corrector = AutoCorrector()
        result = corrector.correct_text("helo world")
        assert "hello" in result
        assert "world" in result
