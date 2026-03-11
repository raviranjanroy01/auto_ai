"""
Desktop G-Board — Active Process Detector
==========================================
Monitors which application is currently focused and adjusts the
inference context mode accordingly.

Key behavior:
  - Code.exe / devenv.exe / pycharm*.exe → "code" mode (technical prompts)
  - chrome.exe / msedge.exe / firefox.exe → "browser" mode
  - WINWORD.EXE / EXCEL.EXE → "office" mode
  - Everything else → "general" mode

The mode affects:
  1. Which system prompt is sent with Cloud API calls
  2. Whether "Code Assist" hotkeys are enabled
  3. N-gram model weights (technical vocab vs general vocab)
"""

import ctypes
import ctypes.wintypes
import threading
import time
import logging
from dataclasses import dataclass
from typing import Optional, Callable

logger = logging.getLogger(__name__)


@dataclass
class ActiveWindowInfo:
    """Information about the currently active window."""
    hwnd: int
    process_name: str       # e.g., "Code.exe"
    window_title: str       # e.g., "main.py - auto_ai - Visual Studio Code"
    context_mode: str       # "code", "browser", "office", "terminal", "general"


# ─── Process → Mode Mapping ─────────────────────────────────────

CODE_PROCESSES = {
    "code.exe", "code - insiders.exe",      # VS Code
    "devenv.exe",                            # Visual Studio
    "pycharm64.exe", "pycharm.exe",          # PyCharm
    "idea64.exe", "idea.exe",                # IntelliJ IDEA
    "clion64.exe", "clion.exe",              # CLion
    "webstorm64.exe", "webstorm.exe",        # WebStorm
    "sublime_text.exe",                      # Sublime Text
    "notepad++.exe",                         # Notepad++
    "atom.exe",                              # Atom
    "cursor.exe",                            # Cursor IDE
}

BROWSER_PROCESSES = {
    "chrome.exe", "msedge.exe", "firefox.exe",
    "brave.exe", "opera.exe", "vivaldi.exe",
    "arc.exe",
}

OFFICE_PROCESSES = {
    "winword.exe", "excel.exe", "powerpnt.exe",
    "onenote.exe", "outlook.exe",
    "libreoffice.exe", "soffice.exe",
}

TERMINAL_PROCESSES = {
    "windowsterminal.exe", "wt.exe",
    "cmd.exe", "powershell.exe", "pwsh.exe",
    "conhost.exe", "alacritty.exe",
    "hyper.exe", "mintty.exe",
}


def classify_process(process_name: str) -> str:
    """Map a process name to a context mode."""
    name = process_name.lower()
    if name in CODE_PROCESSES:
        return "code"
    if name in BROWSER_PROCESSES:
        return "browser"
    if name in OFFICE_PROCESSES:
        return "office"
    if name in TERMINAL_PROCESSES:
        return "terminal"
    return "general"


# ─── Win32 API Helpers ───────────────────────────────────────────

def get_foreground_window_info() -> Optional[ActiveWindowInfo]:
    """Get information about the currently focused window."""
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        # Get foreground window handle
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None

        # Get window title
        title_length = user32.GetWindowTextLengthW(hwnd)
        title_buffer = ctypes.create_unicode_buffer(title_length + 1)
        user32.GetWindowTextW(hwnd, title_buffer, title_length + 1)
        window_title = title_buffer.value

        # Get process ID
        pid = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

        # Get process name from PID
        process_name = _get_process_name(pid.value)

        # Classify context mode
        mode = classify_process(process_name)

        return ActiveWindowInfo(
            hwnd=hwnd,
            process_name=process_name,
            window_title=window_title,
            context_mode=mode,
        )

    except Exception as e:
        logger.debug("Failed to get foreground window info: %s", e)
        return None


def _get_process_name(pid: int) -> str:
    """Get the executable name for a given process ID."""
    try:
        import psutil
        proc = psutil.Process(pid)
        return proc.name()
    except ImportError:
        # Fallback: use Win32 API directly
        return _get_process_name_win32(pid)
    except Exception:
        return "unknown.exe"


def _get_process_name_win32(pid: int) -> str:
    """Get process name using Win32 API (no psutil dependency)."""
    try:
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        kernel32 = ctypes.windll.kernel32

        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return "unknown.exe"

        try:
            # QueryFullProcessImageNameW
            buffer = ctypes.create_unicode_buffer(512)
            size = ctypes.wintypes.DWORD(512)
            if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                # Extract just the filename from the full path
                path = buffer.value
                return path.rsplit("\\", 1)[-1] if "\\" in path else path
        finally:
            kernel32.CloseHandle(handle)

    except Exception:
        pass
    return "unknown.exe"


# ─── Process Monitor Thread ─────────────────────────────────────

class ProcessMonitor:
    """
    Background thread that monitors the active window and notifies
    when the context mode changes (e.g., user switches from VS Code
    to Chrome).
    """

    def __init__(self, poll_interval_ms: int = 250):
        self._interval = poll_interval_ms / 1000.0
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._callback: Optional[Callable[[ActiveWindowInfo], None]] = None
        self._last_info: Optional[ActiveWindowInfo] = None

    def start(self, callback: Callable[[ActiveWindowInfo], None]):
        """Start monitoring. Callback fires when the active window changes."""
        self._callback = callback
        self._running = True
        self._thread = threading.Thread(
            target=self._poll_loop,
            daemon=True,
            name="ProcessMonitor"
        )
        self._thread.start()
        logger.info("Process monitor started (polling every %dms).", int(self._interval * 1000))

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    def _poll_loop(self):
        while self._running:
            info = get_foreground_window_info()
            if info and self._has_changed(info):
                self._last_info = info
                logger.info("Active window changed: [%s] %s → mode=%s",
                          info.process_name, info.window_title[:50], info.context_mode)
                if self._callback:
                    self._callback(info)
            time.sleep(self._interval)

    def _has_changed(self, info: ActiveWindowInfo) -> bool:
        if not self._last_info:
            return True
        return info.hwnd != self._last_info.hwnd

    @property
    def current_mode(self) -> str:
        """Get the current context mode."""
        return self._last_info.context_mode if self._last_info else "general"

    @property
    def current_info(self) -> Optional[ActiveWindowInfo]:
        return self._last_info
