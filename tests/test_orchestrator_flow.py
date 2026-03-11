"""
Integration tests for the Orchestrator keystroke flow.

Tests the full pipeline:
  typing → context tracking → auto-complete → autocorrect → undo

These tests mock the keyboard controller and inference engine to
isolate the orchestrator logic without needing real OS hooks.
"""

import sys
import os
import time
import threading

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from core.hook_bridge import KeyEvent, VK
from core.context_manager import ContextManager
from core.orchestrator import Orchestrator


# ─── Helpers ─────────────────────────────────────────────────────

def make_char_event(char: str) -> KeyEvent:
    """Create a keydown event for a printable character."""
    vk = ord(char.upper()) if char.isalpha() else ord(char)
    return KeyEvent(
        vk_code=vk,
        scan_code=0,
        flags=0,
        timestamp=time.time(),
        is_keydown=True,
        character=char,
    )


def make_space_event() -> KeyEvent:
    return KeyEvent(
        vk_code=VK.SPACE,
        scan_code=0,
        flags=0,
        timestamp=time.time(),
        is_keydown=True,
        character=" ",
    )


def make_backspace_event() -> KeyEvent:
    return KeyEvent(
        vk_code=VK.BACKSPACE,
        scan_code=0,
        flags=0,
        timestamp=time.time(),
        is_keydown=True,
        character="",
    )


def make_enter_event() -> KeyEvent:
    return KeyEvent(
        vk_code=VK.ENTER,
        scan_code=0,
        flags=0,
        timestamp=time.time(),
        is_keydown=True,
        character="",
    )


# ─── Fixtures ───────────────────────────────────────────────────

@pytest.fixture
def orchestrator():
    """
    Create an Orchestrator with mocked subsystems.

    Everything is wired up except:
      - No real keyboard hook (we call _on_key_event directly)
      - No real keyboard controller (mocked to avoid sending real keystrokes)
      - No real caret tracker (mocked)
    """
    orch = Orchestrator.__new__(Orchestrator)
    orch._config = {}
    orch._is_running = True
    orch._is_simulating = False
    orch._sim_timer = None
    orch._modifier_state = {VK.CTRL: False, VK.SHIFT: False, VK.ALT: False}

    # Real context manager (we test its state)
    orch.context_manager = ContextManager()
    orch.context_manager.set_active_window("test_window", "Test", "test.exe")

    # Mock keyboard controller — capture what would be typed
    orch.kb_controller = MagicMock()

    # Mock inference engine
    orch.inference_engine = MagicMock()
    orch.inference_engine.local = MagicMock()
    orch.inference_engine.cloud = MagicMock()
    orch.inference_engine.cloud.is_available = False
    # Default: no completions or next-word predictions
    orch.inference_engine.local.complete_word.return_value = []
    mock_result = MagicMock()
    mock_result.predictions = []
    orch.inference_engine.infer.return_value = mock_result

    # Mock dictionary
    orch.dictionary = MagicMock()
    orch.dictionary.contains.return_value = False  # Default: word not in dictionary

    # No user learning in tests
    orch.learner = None
    orch.predictor = None
    orch.corrector = None

    # Mock process monitor
    orch.process_monitor = MagicMock()
    orch.process_monitor.current_mode = "general"

    # Mock caret tracker
    orch.caret_tracker = MagicMock()
    orch._last_caret_x = 100
    orch._last_caret_y = 100

    # Predictions cache
    orch._predictions = []

    # Undo state
    orch._last_correction = None

    # No UI callbacks
    orch._on_predictions_updated = None
    orch._on_correction_made = None
    orch._on_code_result = None
    orch._on_caret_moved = None

    return orch


def type_word(orch: Orchestrator, word: str):
    """Simulate typing a word character by character."""
    for char in word:
        orch._on_key_event(make_char_event(char))


# ─── Tests: Basic Context Tracking ──────────────────────────────

class TestBasicContext:
    """Test that typing characters correctly updates the context buffer."""

    def test_typing_characters(self, orchestrator):
        """Characters are added to context buffer."""
        type_word(orchestrator, "hello")
        assert orchestrator.context_manager.get_current_word() == "hello"

    def test_space_records_separator(self, orchestrator):
        """Space records separator in context and clears current word."""
        type_word(orchestrator, "hello")
        orchestrator._on_key_event(make_space_event())
        assert orchestrator.context_manager.get_current_word() == ""
        ctx = orchestrator.context_manager.get_context()
        assert "hello " in ctx

    def test_backspace_removes_char(self, orchestrator):
        """Backspace removes the last character from context."""
        type_word(orchestrator, "hello")
        orchestrator._on_key_event(make_backspace_event())
        assert orchestrator.context_manager.get_current_word() == "hell"

    def test_multiple_words(self, orchestrator):
        """Multiple words are tracked in the context buffer."""
        type_word(orchestrator, "I")
        orchestrator._on_key_event(make_space_event())
        type_word(orchestrator, "am")
        orchestrator._on_key_event(make_space_event())
        type_word(orchestrator, "happy")
        assert orchestrator.context_manager.get_current_word() == "happy"
        ctx = orchestrator.context_manager.get_context()
        assert "I am " in ctx

    def test_enter_is_word_boundary(self, orchestrator):
        """Enter acts as a word boundary like space."""
        type_word(orchestrator, "hello")
        orchestrator._on_key_event(make_enter_event())
        assert orchestrator.context_manager.get_current_word() == ""

    def test_typing_clears_undo(self, orchestrator):
        """Typing a character clears the undo state."""
        orchestrator._last_correction = ("hel", "hello", " ")
        orchestrator._on_key_event(make_char_event("a"))
        assert orchestrator._last_correction is None


# ─── Tests: Auto-Complete on Space ───────────────────────────────

class TestAutoComplete:
    """Test auto-completion when space is pressed."""

    def test_auto_complete_replaces_word(self, orchestrator):
        """
        Auto-complete replaces a partial word with the top prediction.
        User types "hel" + space → should auto-complete to "hello".
        """
        type_word(orchestrator, "hel")

        # Set up predictions (simulating what _update_predictions would set)
        orchestrator._predictions = [("hello", 0.8), ("help", 0.6)]
        # "hel" is NOT a valid dictionary word
        orchestrator.dictionary.contains.return_value = False

        orchestrator._on_key_event(make_space_event())

        # _replace_word should have been called (via kb_controller)
        assert orchestrator.kb_controller.type.called
        # Context should now have "hello " (replacement + separator)
        ctx = orchestrator.context_manager.get_context()
        assert "hello " in ctx
        assert orchestrator.context_manager.get_current_word() == ""

    def test_auto_complete_sets_undo(self, orchestrator):
        """Auto-complete stores undo info for backspace reversal."""
        type_word(orchestrator, "hel")
        orchestrator._predictions = [("hello", 0.8)]
        orchestrator.dictionary.contains.return_value = False

        orchestrator._on_key_event(make_space_event())

        assert orchestrator._last_correction == ("hel", "hello", " ")

    def test_no_auto_complete_for_valid_word(self, orchestrator):
        """
        Valid dictionary words should NOT be auto-completed.
        "the" should stay as "the", not become "there".
        """
        type_word(orchestrator, "the")
        orchestrator._predictions = [("there", 0.8), ("them", 0.6)]
        # "the" IS a valid dictionary word
        orchestrator.dictionary.contains.return_value = True

        orchestrator._on_key_event(make_space_event())

        # Context should have "the " (original, not "there ")
        ctx = orchestrator.context_manager.get_context()
        assert "the " in ctx
        assert "there" not in ctx

    def test_no_auto_complete_below_threshold(self, orchestrator):
        """Predictions with score ≤ 0.5 should not trigger auto-complete."""
        type_word(orchestrator, "hel")
        orchestrator._predictions = [("hello", 0.3)]  # Below 0.5 threshold
        orchestrator.dictionary.contains.return_value = False

        orchestrator._on_key_event(make_space_event())

        # Context should have "hel " (original, not "hello ")
        ctx = orchestrator.context_manager.get_context()
        assert "hel " in ctx

    def test_no_auto_complete_for_single_char(self, orchestrator):
        """Single-character words should not trigger auto-complete."""
        type_word(orchestrator, "h")
        orchestrator._predictions = [("hello", 0.9)]

        orchestrator._on_key_event(make_space_event())

        ctx = orchestrator.context_manager.get_context()
        assert "h " in ctx

    def test_no_auto_complete_when_same_word(self, orchestrator):
        """If prediction equals the typed word, don't 'auto-complete' it."""
        type_word(orchestrator, "hello")
        orchestrator._predictions = [("hello", 0.9)]
        orchestrator.dictionary.contains.return_value = False

        orchestrator._on_key_event(make_space_event())

        # No replacement needed — word is already complete
        ctx = orchestrator.context_manager.get_context()
        assert "hello " in ctx

    def test_auto_complete_context_after_preceding_text(self, orchestrator):
        """
        Context should be correct after auto-complete with preceding text.
        "I am hel" + space → context should be "I am hello "
        """
        type_word(orchestrator, "I")
        orchestrator._on_key_event(make_space_event())
        type_word(orchestrator, "am")
        orchestrator._on_key_event(make_space_event())
        type_word(orchestrator, "hel")

        orchestrator._predictions = [("hello", 0.8)]
        orchestrator.dictionary.contains.return_value = False

        orchestrator._on_key_event(make_space_event())

        ctx = orchestrator.context_manager.get_context()
        assert "I am hello " in ctx


# ─── Tests: Autocorrect on Space ─────────────────────────────────

class TestAutocorrect:
    """Test autocorrection when space is pressed (no matching auto-complete)."""

    def test_autocorrect_misspelled_word(self, orchestrator):
        """Misspelled word gets corrected on space."""
        type_word(orchestrator, "teh")
        orchestrator._predictions = []  # No auto-complete match
        orchestrator.dictionary.contains.return_value = False

        # Mock autocorrect: "teh" → "the"
        mock_result = MagicMock()
        mock_result.predictions = [("the", 0.9)]
        orchestrator.inference_engine.infer.return_value = mock_result

        orchestrator._on_key_event(make_space_event())

        ctx = orchestrator.context_manager.get_context()
        assert "the " in ctx
        assert orchestrator._last_correction == ("teh", "the", " ")

    def test_no_autocorrect_for_correct_word(self, orchestrator):
        """Correctly spelled words should not be autocorrected."""
        type_word(orchestrator, "hello")
        orchestrator._predictions = []

        # Mock autocorrect returns same word (no correction)
        mock_result = MagicMock()
        mock_result.predictions = [("hello", 1.0)]
        orchestrator.inference_engine.infer.return_value = mock_result

        orchestrator._on_key_event(make_space_event())

        ctx = orchestrator.context_manager.get_context()
        assert "hello " in ctx
        assert orchestrator._last_correction is None


# ─── Tests: Undo Correction ─────────────────────────────────────

class TestUndoCorrection:
    """Test backspace-to-undo after auto-complete/autocorrect."""

    def test_undo_reverts_context(self, orchestrator):
        """
        Pressing backspace after auto-complete reverts context.
        "hel" → auto-complete → "hello " → backspace → "hel "
        """
        type_word(orchestrator, "hel")
        orchestrator._predictions = [("hello", 0.9)]
        orchestrator.dictionary.contains.return_value = False

        # Trigger auto-complete
        orchestrator._on_key_event(make_space_event())
        assert "hello " in orchestrator.context_manager.get_context()

        # Clear simulating flag (in real usage, 80ms timer expires naturally)
        orchestrator._clear_simulating()

        # Trigger undo
        orchestrator._on_key_event(make_backspace_event())

        ctx = orchestrator.context_manager.get_context()
        assert "hel " in ctx
        assert orchestrator._last_correction is None  # Undo clears itself

    def test_undo_after_autocorrect(self, orchestrator):
        """Undo also works for autocorrect, not just auto-complete."""
        type_word(orchestrator, "teh")
        orchestrator._predictions = []

        mock_result = MagicMock()
        mock_result.predictions = [("the", 0.9)]
        orchestrator.inference_engine.infer.return_value = mock_result

        orchestrator._on_key_event(make_space_event())
        assert "the " in orchestrator.context_manager.get_context()

        orchestrator._clear_simulating()
        orchestrator._on_key_event(make_backspace_event())

        ctx = orchestrator.context_manager.get_context()
        assert "teh " in ctx

    def test_undo_preserves_preceding_text(self, orchestrator):
        """
        Undo should not corrupt text before the corrected word.
        "I am hel" → "I am hello " → undo → "I am hel "
        """
        type_word(orchestrator, "I")
        orchestrator._on_key_event(make_space_event())
        type_word(orchestrator, "am")
        orchestrator._on_key_event(make_space_event())
        type_word(orchestrator, "hel")

        orchestrator._predictions = [("hello", 0.9)]
        orchestrator.dictionary.contains.return_value = False

        orchestrator._on_key_event(make_space_event())
        assert "I am hello " in orchestrator.context_manager.get_context()

        orchestrator._clear_simulating()
        orchestrator._on_key_event(make_backspace_event())

        ctx = orchestrator.context_manager.get_context()
        assert "I am hel " in ctx

    def test_double_backspace_after_undo(self, orchestrator):
        """
        After an undo, further backspaces work normally.
        "hel" → "hello " → undo → "hel " → backspace → "hel"
        """
        type_word(orchestrator, "hel")
        orchestrator._predictions = [("hello", 0.9)]
        orchestrator.dictionary.contains.return_value = False

        orchestrator._on_key_event(make_space_event())
        orchestrator._clear_simulating()
        orchestrator._on_key_event(make_backspace_event())  # undo

        # Further backspace should remove last char normally
        orchestrator._clear_simulating()
        orchestrator._on_key_event(make_backspace_event())
        ctx = orchestrator.context_manager.get_context()
        # After undo: "hel ", after backspace: "hel" (removed the space)
        assert ctx.endswith("hel")

    def test_no_undo_after_typing(self, orchestrator):
        """Typing a character after correction clears undo."""
        type_word(orchestrator, "hel")
        orchestrator._predictions = [("hello", 0.9)]
        orchestrator.dictionary.contains.return_value = False

        orchestrator._on_key_event(make_space_event())
        assert orchestrator._last_correction is not None

        # Clear simulating flag (timer would expire naturally)
        orchestrator._clear_simulating()

        # Type another character — clears undo
        orchestrator._on_key_event(make_char_event("w"))
        assert orchestrator._last_correction is None


# ─── Tests: accept_prediction (click on overlay) ────────────────

class TestAcceptPrediction:
    """Test clicking a suggestion in the overlay."""

    def test_accept_removes_partial_and_adds_full(self, orchestrator):
        """
        Clicking a prediction replaces partial word with full word.
        Context: "hel" → accept "hello" → context should be "hello ", not "helhello ".
        """
        type_word(orchestrator, "hel")
        assert orchestrator.context_manager.get_current_word() == "hel"

        orchestrator.accept_prediction("hello")

        ctx = orchestrator.context_manager.get_context()
        assert "hello " in ctx
        assert "helhello" not in ctx
        assert orchestrator.context_manager.get_current_word() == ""

    def test_accept_with_preceding_text(self, orchestrator):
        """Accept prediction preserves text before the partial word."""
        type_word(orchestrator, "I")
        orchestrator._on_key_event(make_space_event())
        type_word(orchestrator, "hel")

        orchestrator.accept_prediction("hello")

        ctx = orchestrator.context_manager.get_context()
        assert "I hello " in ctx


# ─── Tests: _is_simulating flag ──────────────────────────────────

class TestSimulatingFlag:
    """Test that the simulating flag correctly ignores injected events."""

    def test_events_ignored_while_simulating(self, orchestrator):
        """Key events are discarded when _is_simulating is True."""
        type_word(orchestrator, "abc")
        assert orchestrator.context_manager.get_current_word() == "abc"

        # Simulate what happens during _replace_word
        orchestrator._is_simulating = True

        # These should be ignored
        orchestrator._on_key_event(make_backspace_event())
        orchestrator._on_key_event(make_backspace_event())
        orchestrator._on_key_event(make_char_event("x"))

        assert orchestrator.context_manager.get_current_word() == "abc"

        orchestrator._is_simulating = False

    def test_end_simulating_clears_after_delay(self, orchestrator):
        """_end_simulating clears the flag after a short delay."""
        orchestrator._begin_simulating()
        assert orchestrator._is_simulating is True

        orchestrator._end_simulating(delay=0.02)
        # Still True immediately after
        assert orchestrator._is_simulating is True

        # Wait for timer to fire
        time.sleep(0.05)
        assert orchestrator._is_simulating is False


# ─── Tests: Predictions Cache ───────────────────────────────────

class TestPredictionsCache:
    """Test that predictions are cached and cleared correctly."""

    def test_predictions_cleared_on_word_boundary(self, orchestrator):
        """Space clears the predictions cache."""
        type_word(orchestrator, "hello")
        orchestrator._predictions = [("hello", 0.9)]

        orchestrator._on_key_event(make_space_event())

        assert orchestrator._predictions == []


# ─── Tests: Edge Cases ──────────────────────────────────────────

class TestEdgeCases:
    """Edge cases and regression tests."""

    def test_empty_word_on_double_space(self, orchestrator):
        """Double space should not crash."""
        orchestrator._on_key_event(make_space_event())
        orchestrator._on_key_event(make_space_event())
        # Should not crash; current word should be empty
        assert orchestrator.context_manager.get_current_word() == ""

    def test_backspace_on_empty_context(self, orchestrator):
        """Backspace with nothing typed should not crash."""
        orchestrator._on_key_event(make_backspace_event())
        assert orchestrator.context_manager.get_current_word() == ""

    def test_sequential_auto_completes(self, orchestrator):
        """
        Two auto-completes in a row should each produce correct context.
        "hel" → "hello " → "wor" → "world "
        """
        # First word
        type_word(orchestrator, "hel")
        orchestrator._predictions = [("hello", 0.9)]
        orchestrator.dictionary.contains.return_value = False
        orchestrator._on_key_event(make_space_event())
        orchestrator._clear_simulating()

        # Second word
        type_word(orchestrator, "wor")
        orchestrator._predictions = [("world", 0.8)]
        orchestrator.dictionary.contains.return_value = False
        orchestrator._on_key_event(make_space_event())

        ctx = orchestrator.context_manager.get_context()
        assert "hello world " in ctx

    def test_auto_complete_then_normal_word(self, orchestrator):
        """
        Auto-complete followed by a normal word.
        "hel" → "hello " → "foo "
        """
        type_word(orchestrator, "hel")
        orchestrator._predictions = [("hello", 0.9)]
        orchestrator.dictionary.contains.return_value = False
        orchestrator._on_key_event(make_space_event())
        orchestrator._clear_simulating()

        type_word(orchestrator, "foo")
        orchestrator._predictions = []
        mock_result = MagicMock()
        mock_result.predictions = [("foo", 1.0)]
        orchestrator.inference_engine.infer.return_value = mock_result
        orchestrator._on_key_event(make_space_event())

        ctx = orchestrator.context_manager.get_context()
        assert "hello foo " in ctx
