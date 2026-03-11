"""
Desktop G-Board — Python-side Hook Bridge
==========================================
Reads raw KeyEvent structs from the C++ hook service via
a Named Pipe and converts them into Python-friendly key events.

Two modes of operation:
  1. NATIVE MODE: Reads from Named Pipe (C++ hook_service.exe running)
  2. FALLBACK MODE: Uses pynput for pure-Python key capture (slower but no build needed)

Usage:
    bridge = HookBridge(mode="fallback")  # or "native" when C++ service is running
    bridge.start(callback=on_key_event)
"""

import struct
import threading
import time
import logging
from typing import Callable, Optional
from dataclasses import dataclass, field
from enum import IntEnum

logger = logging.getLogger(__name__)


# ─── Key Event Data ──────────────────────────────────────────────

class VK(IntEnum):
    """Common Virtual Key codes (subset — full list in WinUser.h)."""
    BACKSPACE = 0x08
    TAB = 0x09
    ENTER = 0x0D
    SHIFT = 0x10
    CTRL = 0x11
    ALT = 0x12
    CAPSLOCK = 0x14
    ESCAPE = 0x1B
    SPACE = 0x20
    LEFT = 0x25
    UP = 0x26
    RIGHT = 0x27
    DOWN = 0x28
    DELETE = 0x2E
    # A-Z = 0x41..0x5A
    # 0-9 = 0x30..0x39
    OEM_PERIOD = 0xBE
    OEM_COMMA = 0xBC
    OEM_7 = 0xDE       # Apostrophe / quote


@dataclass
class KeyEvent:
    """Python representation of a key event from the hook."""
    vk_code: int
    scan_code: int
    flags: int
    timestamp: float        # Seconds since epoch
    is_keydown: bool
    character: str = ""     # Resolved character (e.g., 'a', 'A', '!')

    @property
    def is_char(self) -> bool:
        """True if this key produces a printable character."""
        return len(self.character) == 1 and self.character.isprintable()

    @property
    def is_space(self) -> bool:
        return self.vk_code == VK.SPACE

    @property
    def is_backspace(self) -> bool:
        return self.vk_code == VK.BACKSPACE

    @property
    def is_enter(self) -> bool:
        return self.vk_code == VK.ENTER

    @property
    def is_word_boundary(self) -> bool:
        """True if this key terminates a word (space, enter, punctuation)."""
        if self.is_space or self.is_enter:
            return True
        if self.is_char and not self.character.isalnum() and self.character != "'":
            return True
        return False


# ─── Named Pipe Reader (Native Mode) ────────────────────────────

# KeyEvent C struct format: uint32 vk, uint32 scan, uint32 flags,
#                            uint64 timestamp, uint8 is_keydown, 3 padding
KEYEVENT_STRUCT_FORMAT = "<IIIQBxxx"
KEYEVENT_STRUCT_SIZE = struct.calcsize(KEYEVENT_STRUCT_FORMAT)  # 24 bytes

PIPE_NAME = r"\\.\pipe\DesktopGBoardKeys"


class NativePipeReader:
    """Reads KeyEvent structs from the C++ hook service Named Pipe."""

    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._pipe_handle = None

    def start(self, callback: Callable[[KeyEvent], None]):
        """Connect to the Named Pipe and start reading in a background thread."""
        self._running = True
        self._thread = threading.Thread(
            target=self._read_loop,
            args=(callback,),
            daemon=True,
            name="HookBridge-NativePipe"
        )
        self._thread.start()

    def stop(self):
        self._running = False
        if self._pipe_handle:
            try:
                import ctypes
                ctypes.windll.kernel32.CloseHandle(self._pipe_handle)
            except Exception:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _read_loop(self, callback: Callable[[KeyEvent], None]):
        """Read raw bytes from the pipe and dispatch KeyEvents."""
        import ctypes
        import ctypes.wintypes

        GENERIC_READ = 0x80000000
        OPEN_EXISTING = 3

        logger.info("Connecting to hook service pipe: %s", PIPE_NAME)

        # Retry connection until the C++ service is running
        while self._running:
            handle = ctypes.windll.kernel32.CreateFileW(
                PIPE_NAME,
                GENERIC_READ,
                0, None, OPEN_EXISTING, 0, None
            )
            if handle != -1:
                self._pipe_handle = handle
                logger.info("Connected to hook service!")
                break
            else:
                logger.debug("Hook service not ready, retrying in 1s...")
                time.sleep(1.0)

        if not self._running:
            return

        # Read loop — each read is exactly KEYEVENT_STRUCT_SIZE bytes
        buffer = ctypes.create_string_buffer(KEYEVENT_STRUCT_SIZE)
        bytes_read = ctypes.wintypes.DWORD()

        while self._running:
            ok = ctypes.windll.kernel32.ReadFile(
                self._pipe_handle,
                buffer,
                KEYEVENT_STRUCT_SIZE,
                ctypes.byref(bytes_read),
                None
            )
            if not ok or bytes_read.value != KEYEVENT_STRUCT_SIZE:
                logger.warning("Pipe read failed or incomplete — service disconnected?")
                break

            # Unpack the raw struct
            vk, scan, flags, ts_ticks, is_down = struct.unpack(
                KEYEVENT_STRUCT_FORMAT, buffer.raw
            )

            # Convert QPC ticks to seconds (approximate)
            timestamp = time.time()  # Use Python time for simplicity

            # Resolve character from virtual key code
            char = self._vk_to_char(vk, flags)

            event = KeyEvent(
                vk_code=vk,
                scan_code=scan,
                flags=flags,
                timestamp=timestamp,
                is_keydown=bool(is_down),
                character=char
            )
            callback(event)

        logger.info("Pipe reader exiting.")

    @staticmethod
    def _vk_to_char(vk: int, flags: int) -> str:
        """Convert a virtual key code to a character string."""
        # A-Z
        if 0x41 <= vk <= 0x5A:
            return chr(vk).lower()
        # 0-9
        if 0x30 <= vk <= 0x39:
            return chr(vk)
        # Space
        if vk == VK.SPACE:
            return " "
        # Common punctuation (simplified — full version would use ToUnicode)
        mapping = {
            VK.OEM_PERIOD: ".",
            VK.OEM_COMMA: ",",
            VK.OEM_7: "'",
        }
        return mapping.get(vk, "")


# ─── Fallback pynput Reader ─────────────────────────────────────

class PynputFallbackReader:
    """
    Pure-Python key capture using pynput.
    Higher latency (~5-10ms) but requires no C++ build.
    """

    def __init__(self):
        self._listener = None
        self._callback = None

    def start(self, callback: Callable[[KeyEvent], None]):
        from pynput import keyboard

        self._callback = callback
        self._listener = keyboard.Listener(
            on_press=lambda key: self._on_key(key, True),
            on_release=lambda key: self._on_key(key, False),
        )
        self._listener.start()
        logger.info("Fallback pynput listener started.")

    def stop(self):
        if self._listener:
            self._listener.stop()
            logger.info("Fallback pynput listener stopped.")

    def _on_key(self, key, is_down: bool):
        from pynput import keyboard as kb

        char = ""
        vk = 0

        if hasattr(key, "char") and key.char:
            char = key.char
            vk = ord(key.char.upper()) if key.char.isalpha() else ord(key.char)
        elif hasattr(key, "vk") and key.vk:
            vk = key.vk
        else:
            # Map special keys
            special_map = {
                kb.Key.space: (VK.SPACE, " "),
                kb.Key.backspace: (VK.BACKSPACE, ""),
                kb.Key.enter: (VK.ENTER, ""),
                kb.Key.tab: (VK.TAB, ""),
                kb.Key.shift: (VK.SHIFT, ""),
                kb.Key.ctrl_l: (VK.CTRL, ""),
                kb.Key.alt_l: (VK.ALT, ""),
                kb.Key.delete: (VK.DELETE, ""),
                kb.Key.esc: (VK.ESCAPE, ""),
            }
            if key in special_map:
                vk, char = special_map[key]

        event = KeyEvent(
            vk_code=vk,
            scan_code=0,
            flags=0,
            timestamp=time.time(),
            is_keydown=is_down,
            character=char,
        )
        if self._callback:
            self._callback(event)


# ─── Unified Hook Bridge ────────────────────────────────────────

class HookBridge:
    """
    Unified keyboard hook bridge.

    Modes:
        "native"   — C++ hook service + Named Pipe (recommended, sub-5ms)
        "fallback" — pynput pure-Python capture (no build needed, ~5-10ms)
    """

    def __init__(self, mode: str = "fallback"):
        if mode == "native":
            self._reader = NativePipeReader()
        elif mode == "fallback":
            self._reader = PynputFallbackReader()
        else:
            raise ValueError(f"Unknown hook mode: {mode!r}. Use 'native' or 'fallback'.")

        self.mode = mode
        logger.info("HookBridge initialized in %s mode.", mode)

    def start(self, callback: Callable[[KeyEvent], None]):
        """Start capturing keystrokes and forwarding to callback."""
        self._reader.start(callback)

    def stop(self):
        """Stop capturing keystrokes."""
        self._reader.stop()
