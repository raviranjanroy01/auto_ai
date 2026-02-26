"""Tests for the user model / personalization."""

import sys
import os
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from user_model import UserProfile, UserLearner


class TestUserProfile:
    """Tests for UserProfile."""

    def test_create_profile(self):
        profile = UserProfile(user_id="test_user")
        assert profile.user_id == "test_user"
        assert len(profile.custom_words) == 0

    def test_add_word(self):
        profile = UserProfile()
        profile.add_word("hello")
        profile.add_word("hello")
        profile.add_word("world")
        assert profile.custom_words["hello"] == 2
        assert profile.custom_words["world"] == 1

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile = UserProfile(user_id="test")
            profile.add_word("python")
            profile.add_word("coding")
            profile.save(directory=tmpdir)

            loaded = UserProfile.load("test", directory=tmpdir)
            assert loaded.custom_words["python"] == 1
            assert loaded.custom_words["coding"] == 1

    def test_frequent_words(self):
        profile = UserProfile()
        for _ in range(10):
            profile.add_word("common")
        for _ in range(3):
            profile.add_word("rare")

        top = profile.get_frequent_words(top_k=1)
        assert top[0][0] == "common"


class TestUserLearner:
    """Tests for UserLearner."""

    def test_learn_from_text(self):
        learner = UserLearner()
        learner.learn_from_text("I love programming in python")
        assert learner.profile.custom_words["python"] == 1
        assert learner.profile.custom_words["love"] == 1

    def test_learn_correction(self):
        learner = UserLearner()
        learner.learn_correction("teh", "the")
        assert learner.profile.corrections["teh"] == "the"

    def test_personal_predictions(self):
        learner = UserLearner()
        learner.learn_from_text("hello world hello world hello world")
        predictions = learner.get_personal_predictions("hello", top_k=3)
        assert len(predictions) > 0
