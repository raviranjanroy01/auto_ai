"""
Desktop G-Board — Context Manager
==================================
Maintains a sliding window buffer of the last 2048 characters
typed across different active windows. Provides "Project Context"
and "Style Context" awareness for the inference engine.

Design:
  - Per-window buffers: Each active window gets its own context ring
  - Global buffer: A merged view of all recent typing for style analysis
  - Thread-safe: All operations are protected by a lock
"""

import threading
import time
import logging
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)

# ─── Constants ───────────────────────────────────────────────────
MAX_CONTEXT_LENGTH = 2048       # Characters per window
MAX_GLOBAL_CONTEXT = 4096       # Characters across all windows
MAX_TRACKED_WINDOWS = 32        # LRU eviction after this many windows
WORD_BOUNDARY_CHARS = {" ", "\n", "\t", ".", ",", ";", ":", "!", "?", "(", ")", "[", "]", "{", "}"}


@dataclass
class WindowContext:
    """Context buffer for a single window/application."""
    window_title: str
    process_name: str
    buffer: str = ""
    last_active: float = field(default_factory=time.time)
    word_count: int = 0

    def append(self, text: str):
        """Append text to this window's buffer, trimming to MAX_CONTEXT_LENGTH."""
        self.buffer += text
        if len(self.buffer) > MAX_CONTEXT_LENGTH:
            # Trim from the front, keeping the most recent text
            self.buffer = self.buffer[-MAX_CONTEXT_LENGTH:]
        self.last_active = time.time()
        self.word_count = len(self.buffer.split())

    def backspace(self, count: int = 1):
        """Remove the last `count` characters from the buffer."""
        if count >= len(self.buffer):
            self.buffer = ""
        else:
            self.buffer = self.buffer[:-count]
        self.last_active = time.time()

    @property
    def last_word(self) -> str:
        """Get the word currently being typed (after the last word boundary)."""
        for i in range(len(self.buffer) - 1, -1, -1):
            if self.buffer[i] in WORD_BOUNDARY_CHARS:
                return self.buffer[i + 1:]
        return self.buffer

    @property
    def last_n_words(self) -> str:
        """Get the last few words for n-gram context."""
        words = self.buffer.split()
        return " ".join(words[-5:]) if words else ""

    @property
    def last_sentence(self) -> str:
        """Get the current sentence being typed."""
        # Find last sentence boundary
        for i in range(len(self.buffer) - 1, -1, -1):
            if self.buffer[i] in {".", "!", "?"}:
                return self.buffer[i + 1:].strip()
        return self.buffer.strip()


class ContextManager:
    """
    Manages typing context across multiple windows.

    Provides:
      - Per-window sliding buffer (2048 chars)
      - Global merged context for style analysis
      - Active window tracking for context-aware predictions
    """

    def __init__(self):
        self._lock = threading.Lock()
        # LRU-ordered dict: window_id -> WindowContext
        self._windows: OrderedDict[str, WindowContext] = OrderedDict()
        self._active_window_id: Optional[str] = None
        self._global_buffer: str = ""

    # ─── Public API ──────────────────────────────────────────────

    def set_active_window(self, window_id: str, title: str = "", process: str = ""):
        """Update which window is currently active."""
        with self._lock:
            self._active_window_id = window_id
            if window_id not in self._windows:
                self._windows[window_id] = WindowContext(
                    window_title=title,
                    process_name=process,
                )
            else:
                # Move to end (most recently used)
                self._windows.move_to_end(window_id)
                ctx = self._windows[window_id]
                if title:
                    ctx.window_title = title
                if process:
                    ctx.process_name = process

            # LRU eviction
            while len(self._windows) > MAX_TRACKED_WINDOWS:
                evicted_id, _ = self._windows.popitem(last=False)
                logger.debug("Evicted window context: %s", evicted_id)

    def on_character(self, char: str):
        """Record a typed character in the active window's buffer."""
        with self._lock:
            ctx = self._get_active_context()
            if ctx:
                ctx.append(char)
                self._global_buffer += char
                if len(self._global_buffer) > MAX_GLOBAL_CONTEXT:
                    self._global_buffer = self._global_buffer[-MAX_GLOBAL_CONTEXT:]

    def on_backspace(self, count: int = 1):
        """Handle backspace in the active window."""
        with self._lock:
            ctx = self._get_active_context()
            if ctx:
                ctx.backspace(count)
                if self._global_buffer:
                    self._global_buffer = self._global_buffer[:-count]

    def on_word_complete(self, word: str):
        """Called when a word boundary is hit. Good time for correction/prediction."""
        # This is a notification hook — the actual text is already in the buffer
        logger.debug("Word completed: %r", word)

    # ─── Context Retrieval ───────────────────────────────────────

    def get_current_word(self) -> str:
        """Get the word currently being typed in the active window."""
        with self._lock:
            ctx = self._get_active_context()
            return ctx.last_word if ctx else ""

    def get_context(self, max_chars: int = 512) -> str:
        """Get the recent context from the active window for prediction."""
        with self._lock:
            ctx = self._get_active_context()
            if not ctx:
                return ""
            return ctx.buffer[-max_chars:]

    def get_full_context(self) -> str:
        """Get the full 2048-char context for the active window."""
        with self._lock:
            ctx = self._get_active_context()
            return ctx.buffer if ctx else ""

    def get_global_context(self) -> str:
        """Get the global context across all windows (style analysis)."""
        with self._lock:
            return self._global_buffer

    def get_ngram_context(self) -> str:
        """Get the last few words for n-gram prediction."""
        with self._lock:
            ctx = self._get_active_context()
            return ctx.last_n_words if ctx else ""

    def get_sentence_context(self) -> str:
        """Get the current sentence being typed (up to the last sentence boundary)."""
        with self._lock:
            ctx = self._get_active_context()
            return ctx.last_sentence if ctx else ""

    def get_active_process(self) -> str:
        """Get the process name of the currently active window."""
        with self._lock:
            ctx = self._get_active_context()
            return ctx.process_name if ctx else ""

    def get_active_title(self) -> str:
        """Get the title of the currently active window."""
        with self._lock:
            ctx = self._get_active_context()
            return ctx.window_title if ctx else ""

    def get_all_window_contexts(self) -> List[Tuple[str, str, int]]:
        """Get a summary of all tracked windows: (id, title, char_count)."""
        with self._lock:
            return [
                (wid, ctx.window_title, len(ctx.buffer))
                for wid, ctx in self._windows.items()
            ]

    def clear_active(self):
        """Clear the context for the active window."""
        with self._lock:
            ctx = self._get_active_context()
            if ctx:
                ctx.buffer = ""

    def clear_all(self):
        """Clear all context buffers."""
        with self._lock:
            self._windows.clear()
            self._global_buffer = ""
            self._active_window_id = None

    # ─── Internal ────────────────────────────────────────────────

    def _get_active_context(self) -> Optional[WindowContext]:
        """Get the WindowContext for the currently active window."""
        if self._active_window_id and self._active_window_id in self._windows:
            return self._windows[self._active_window_id]
        return None
