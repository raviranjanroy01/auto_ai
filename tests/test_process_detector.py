"""Tests for the Process Detector."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.process_detector import classify_process


class TestProcessDetector:
    """Tests for process classification."""

    def test_code_processes(self):
        assert classify_process("Code.exe") == "code"
        assert classify_process("devenv.exe") == "code"
        assert classify_process("pycharm64.exe") == "code"
        assert classify_process("sublime_text.exe") == "code"

    def test_browser_processes(self):
        assert classify_process("chrome.exe") == "browser"
        assert classify_process("msedge.exe") == "browser"
        assert classify_process("firefox.exe") == "browser"

    def test_office_processes(self):
        assert classify_process("WINWORD.EXE") == "office"
        assert classify_process("EXCEL.EXE") == "office"

    def test_terminal_processes(self):
        assert classify_process("WindowsTerminal.exe") == "terminal"
        assert classify_process("powershell.exe") == "terminal"

    def test_general_fallback(self):
        assert classify_process("notepad.exe") == "general"
        assert classify_process("unknown_app.exe") == "general"

    def test_case_insensitive(self):
        assert classify_process("CODE.EXE") == "code"
        assert classify_process("Chrome.exe") == "browser"
