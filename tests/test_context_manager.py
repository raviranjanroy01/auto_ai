"""Tests for the Context Manager."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.context_manager import ContextManager


class TestContextManager:
    """Tests for the sliding window context buffer."""

    def test_basic_character_input(self):
        cm = ContextManager()
        cm.set_active_window("win1", title="Notepad", process="notepad.exe")
        cm.on_character("h")
        cm.on_character("e")
        cm.on_character("l")
        cm.on_character("l")
        cm.on_character("o")
        assert cm.get_current_word() == "hello"

    def test_word_boundary(self):
        cm = ContextManager()
        cm.set_active_window("win1")
        for c in "hello ":
            cm.on_character(c)
        assert cm.get_current_word() == ""
        assert "hello" in cm.get_context()

    def test_backspace(self):
        cm = ContextManager()
        cm.set_active_window("win1")
        for c in "helo":
            cm.on_character(c)
        cm.on_backspace()
        assert cm.get_current_word() == "hel"

    def test_multi_window_context(self):
        cm = ContextManager()
        cm.set_active_window("win1", title="Notepad")
        for c in "hello ":
            cm.on_character(c)

        cm.set_active_window("win2", title="VS Code")
        for c in "code ":
            cm.on_character(c)

        # Switch back to win1
        cm.set_active_window("win1")
        assert "hello" in cm.get_context()

    def test_sliding_window_limit(self):
        cm = ContextManager()
        cm.set_active_window("win1")
        # Type more than 2048 chars
        long_text = "a" * 3000
        for c in long_text:
            cm.on_character(c)
        assert len(cm.get_full_context()) <= 2048

    def test_global_context(self):
        cm = ContextManager()
        cm.set_active_window("win1")
        for c in "hello ":
            cm.on_character(c)
        cm.set_active_window("win2")
        for c in "world ":
            cm.on_character(c)
        global_ctx = cm.get_global_context()
        assert "hello" in global_ctx
        assert "world" in global_ctx

    def test_clear(self):
        cm = ContextManager()
        cm.set_active_window("win1")
        for c in "test":
            cm.on_character(c)
        cm.clear_active()
        assert cm.get_full_context() == ""

    def test_process_tracking(self):
        cm = ContextManager()
        cm.set_active_window("win1", process="code.exe")
        assert cm.get_active_process() == "code.exe"
