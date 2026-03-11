"""
Desktop G-Board — Caret (Text Cursor) Tracker
===============================================
Tracks the screen position of the text cursor so the prediction
overlay can follow it.

Strategy:
  1. PRIMARY: Use GetGUIThreadInfo() for standard Win32 apps
     (Notepad, WordPad, Office, etc.). Fast and reliable.

  2. FALLBACK: Use Microsoft UI Automation (UIA) for "windowless"
     apps like Chrome, Discord, VS Code, Electron-based editors.
     Standard APIs return (0,0) for these — UIA is the ONLY reliable
     way to get cursor coordinates in modern software.

  3. LAST RESORT: Use GetCaretPos() (least reliable, often wrong).

Usage:
    tracker = CaretTracker()
    x, y, height = tracker.get_caret_position()
"""

import ctypes
import ctypes.wintypes
import logging
import threading
import time
from dataclasses import dataclass
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


# ─── Win32 Structures ───────────────────────────────────────────

class GUITHREADINFO(ctypes.Structure):
    """Win32 GUITHREADINFO structure for GetGUIThreadInfo()."""
    _fields_ = [
        ("cbSize",        ctypes.wintypes.DWORD),
        ("flags",         ctypes.wintypes.DWORD),
        ("hwndActive",    ctypes.wintypes.HWND),
        ("hwndFocus",     ctypes.wintypes.HWND),
        ("hwndCapture",   ctypes.wintypes.HWND),
        ("hwndMenuOwner", ctypes.wintypes.HWND),
        ("hwndMoveSize",  ctypes.wintypes.HWND),
        ("hwndCaret",     ctypes.wintypes.HWND),
        ("rcCaret",       ctypes.wintypes.RECT),
    ]


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


@dataclass
class CaretPosition:
    """Screen-space position of the text caret."""
    x: int          # Screen X coordinate
    y: int          # Screen Y coordinate (top of caret)
    height: int     # Caret height in pixels
    method: str     # Which method found it ("gui_thread", "uia", "caret_pos", "none")
    confidence: float = 1.0  # 0.0-1.0 confidence in position accuracy

    @property
    def bottom(self) -> int:
        return self.y + self.height

    @property
    def is_valid(self) -> bool:
        return self.method != "none" and (self.x != 0 or self.y != 0)


class CaretTracker:
    """
    Multi-strategy caret position tracker.

    Tries GetGUIThreadInfo first, then UI Automation, then GetCaretPos.
    Returns the best available position for overlay placement.
    """

    def __init__(self):
        self._user32 = ctypes.windll.user32
        self._uia_available = False
        self._uia_automation = None

        # Try to initialize UI Automation
        try:
            import comtypes.client
            self._uia_automation = comtypes.client.CreateObject(
                "{ff48dba4-60ef-4201-aa87-54103eef594e}",  # CUIAutomation
                interface=None
            )
            self._uia_available = True
            logger.info("UI Automation initialized successfully.")
        except Exception as e:
            logger.warning("UI Automation not available: %s. "
                         "Chrome/VS Code caret tracking will be limited.", e)

    def get_caret_position(self) -> CaretPosition:
        """
        Get the current caret position using the best available method.

        Returns a CaretPosition with screen coordinates.
        """
        # Strategy 1: GetGUIThreadInfo (fast, works for native Win32 apps)
        pos = self._try_gui_thread_info()
        if pos and pos.is_valid:
            return pos

        # Strategy 2: UI Automation (slower, but works for Chrome/VS Code/Electron)
        if self._uia_available:
            pos = self._try_uia()
            if pos and pos.is_valid:
                return pos

        # Strategy 3: GetCaretPos (last resort, often returns wrong values)
        pos = self._try_get_caret_pos()
        if pos and pos.is_valid:
            return pos

        # No caret found — return invalid position
        return CaretPosition(x=0, y=0, height=20, method="none", confidence=0.0)

    # ─── Strategy 1: GetGUIThreadInfo ────────────────────────────

    def _try_gui_thread_info(self) -> Optional[CaretPosition]:
        """
        Use GetGUIThreadInfo to find the caret in the foreground window.
        Works well for: Notepad, WordPad, Office, WPF apps.
        Fails for: Chrome, Firefox, VS Code, Electron apps (returns 0,0).
        """
        try:
            # Get the foreground window's thread ID
            hwnd = self._user32.GetForegroundWindow()
            thread_id = self._user32.GetWindowThreadProcessId(hwnd, None)

            gui_info = GUITHREADINFO()
            gui_info.cbSize = ctypes.sizeof(GUITHREADINFO)

            if not self._user32.GetGUIThreadInfo(thread_id, ctypes.byref(gui_info)):
                return None

            # Check if there's a caret window
            if not gui_info.hwndCaret:
                return None

            rc = gui_info.rcCaret
            x, y = rc.left, rc.top
            height = max(rc.bottom - rc.top, 16)

            # Convert from client coordinates to screen coordinates
            point = POINT(x, y)
            self._user32.ClientToScreen(gui_info.hwndCaret, ctypes.byref(point))

            return CaretPosition(
                x=point.x,
                y=point.y,
                height=height,
                method="gui_thread",
                confidence=0.95
            )

        except Exception as e:
            logger.debug("GetGUIThreadInfo failed: %s", e)
            return None

    # ─── Strategy 2: UI Automation ───────────────────────────────

    def _try_uia(self) -> Optional[CaretPosition]:
        """
        Use Microsoft UI Automation to find the caret.
        This is the ONLY reliable method for:
          - Chrome, Edge, Firefox (browser-rendered text fields)
          - VS Code, Discord, Slack (Electron apps)
          - Any "windowless" control

        UIA exposes the TextPattern interface which provides
        the bounding rectangle of the text insertion point.
        """
        if not self._uia_automation:
            return None

        try:
            import comtypes.client
            from comtypes import COMError

            # IUIAutomation interface
            uia = self._uia_automation

            # Get the focused element
            focused = uia.GetFocusedElement()
            if not focused:
                return None

            # Try to get TextPattern2 first (richer), then TextPattern
            # TextPattern.ID = 10014, TextPattern2.ID = 10024
            text_pattern = None
            for pattern_id in [10024, 10014]:
                try:
                    text_pattern = focused.GetCurrentPattern(pattern_id)
                    if text_pattern:
                        break
                except (COMError, Exception):
                    continue

            if not text_pattern:
                # Try ValuePattern as fallback (for simple text fields)
                return None

            # Get the selection/caret range
            try:
                ranges = text_pattern.GetSelection()
                if ranges and ranges.Length > 0:
                    text_range = ranges.GetElement(0)
                    # Get bounding rectangles
                    rects = text_range.GetBoundingRectangles()
                    if rects and len(rects) >= 4:
                        x, y, w, h = int(rects[0]), int(rects[1]), int(rects[2]), int(rects[3])
                        return CaretPosition(
                            x=x + w,  # Right edge of selection = caret
                            y=y,
                            height=max(h, 16),
                            method="uia",
                            confidence=0.85
                        )
            except (COMError, Exception) as e:
                logger.debug("UIA TextPattern query failed: %s", e)
                return None

        except Exception as e:
            logger.debug("UIA failed: %s", e)
            return None

    # ─── Strategy 3: GetCaretPos (Last Resort) ───────────────────

    def _try_get_caret_pos(self) -> Optional[CaretPosition]:
        """
        Use GetCaretPos — works only if the calling thread owns the caret.
        Usually unreliable for global hooks but worth trying as last resort.
        """
        try:
            point = POINT()
            if self._user32.GetCaretPos(ctypes.byref(point)):
                # Convert to screen coords
                hwnd = self._user32.GetForegroundWindow()
                self._user32.ClientToScreen(hwnd, ctypes.byref(point))

                return CaretPosition(
                    x=point.x,
                    y=point.y,
                    height=20,  # Assume default height
                    method="caret_pos",
                    confidence=0.5
                )
        except Exception as e:
            logger.debug("GetCaretPos failed: %s", e)

        return None


class CaretPollingThread:
    """
    Background thread that periodically polls the caret position
    and notifies the UI overlay when it moves.
    """

    def __init__(self, tracker: CaretTracker, interval_ms: int = 50):
        self._tracker = tracker
        self._interval = interval_ms / 1000.0
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._callback = None
        self._last_pos: Optional[CaretPosition] = None

    def start(self, callback):
        """Start polling. Callback receives CaretPosition when it changes."""
        self._callback = callback
        self._running = True
        self._thread = threading.Thread(
            target=self._poll_loop,
            daemon=True,
            name="CaretPoller"
        )
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    def _poll_loop(self):
        while self._running:
            pos = self._tracker.get_caret_position()
            if self._should_notify(pos):
                self._last_pos = pos
                if self._callback:
                    self._callback(pos)
            time.sleep(self._interval)

    def _should_notify(self, pos: CaretPosition) -> bool:
        """Only notify when the caret has actually moved."""
        if not self._last_pos:
            return pos.is_valid
        if not pos.is_valid:
            return False
        return (
            abs(pos.x - self._last_pos.x) > 2 or
            abs(pos.y - self._last_pos.y) > 2
        )
