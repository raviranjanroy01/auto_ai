"""
Desktop G-Board — System Tray Application
===========================================
Runs the Desktop G-Board as a system tray icon with:
  - Start/Stop toggle
  - Settings submenu
  - Status indicator (green=active, yellow=idle, red=error)
  - "Start on boot" option (Windows Registry)

Implementation uses pystray for cross-framework tray support.
Falls back to a simple console mode if pystray is not available.
"""

import os
import sys
import time
import winreg
import logging
import threading
from typing import Optional, Callable

logger = logging.getLogger(__name__)

# ─── Constants ───────────────────────────────────────────────────
APP_NAME = "Desktop G-Board"
APP_VERSION = "0.2.0"
REGISTRY_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
REGISTRY_VALUE_NAME = "DesktopGBoard"


class SystemTrayApp:
    """
    System tray application wrapper.
    Manages the tray icon, menu, and start-on-boot functionality.
    """

    def __init__(self,
                 on_start: Optional[Callable] = None,
                 on_stop: Optional[Callable] = None,
                 on_settings: Optional[Callable] = None,
                 on_quit: Optional[Callable] = None):
        self._on_start = on_start
        self._on_stop = on_stop
        self._on_settings = on_settings
        self._on_quit = on_quit
        self._is_active = False
        self._tray_icon = None
        self._use_pystray = False

        try:
            import pystray
            from PIL import Image
            self._use_pystray = True
        except ImportError:
            logger.warning("pystray/Pillow not installed. System tray will not be available. "
                         "Install with: pip install pystray Pillow")

    def run(self):
        """Start the system tray application."""
        if self._use_pystray:
            self._run_pystray()
        else:
            self._run_console_fallback()

    def set_active(self, active: bool):
        """Update the tray icon to reflect active/inactive state."""
        self._is_active = active
        if self._tray_icon and self._use_pystray:
            self._tray_icon.icon = self._create_icon(
                color=(0, 200, 80) if active else (200, 200, 0)
            )

    def set_error(self):
        """Show error state in the tray icon."""
        if self._tray_icon and self._use_pystray:
            self._tray_icon.icon = self._create_icon(color=(200, 50, 50))

    def notify(self, title: str, message: str):
        """Show a system notification."""
        if self._tray_icon and self._use_pystray:
            self._tray_icon.notify(message, title)

    # ─── Start on Boot ───────────────────────────────────────────

    @staticmethod
    def is_start_on_boot_enabled() -> bool:
        """Check if the app is set to start on Windows boot."""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_KEY, 0, winreg.KEY_READ)
            try:
                value, _ = winreg.QueryValueEx(key, REGISTRY_VALUE_NAME)
                return bool(value)
            except FileNotFoundError:
                return False
            finally:
                winreg.CloseKey(key)
        except Exception:
            return False

    @staticmethod
    def set_start_on_boot(enabled: bool):
        """Enable or disable start on Windows boot via registry."""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_KEY, 0, winreg.KEY_SET_VALUE)
            if enabled:
                # Get the path to the main script
                script_path = os.path.abspath(sys.argv[0])
                python_path = sys.executable
                cmd = f'"{python_path}" "{script_path}"'
                winreg.SetValueEx(key, REGISTRY_VALUE_NAME, 0, winreg.REG_SZ, cmd)
                logger.info("Start on boot ENABLED: %s", cmd)
            else:
                try:
                    winreg.DeleteValue(key, REGISTRY_VALUE_NAME)
                    logger.info("Start on boot DISABLED.")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            logger.error("Failed to modify start-on-boot registry: %s", e)

    # ─── pystray Implementation ──────────────────────────────────

    def _run_pystray(self):
        """Run the system tray using pystray."""
        import pystray
        from pystray import MenuItem, Menu

        def on_toggle(icon, item):
            if self._is_active:
                self._is_active = False
                if self._on_stop:
                    self._on_stop()
                self.set_active(False)
            else:
                self._is_active = True
                if self._on_start:
                    self._on_start()
                self.set_active(True)

        def on_boot_toggle(icon, item):
            current = self.is_start_on_boot_enabled()
            self.set_start_on_boot(not current)

        def on_settings(icon, item):
            if self._on_settings:
                self._on_settings()

        def on_quit(icon, item):
            if self._on_quit:
                self._on_quit()
            icon.stop()

        menu = Menu(
            MenuItem(
                lambda text: "⏸ Pause G-Board" if self._is_active else "▶ Start G-Board",
                on_toggle,
                default=True,  # Double-click action
            ),
            Menu.SEPARATOR,
            MenuItem("⚙ Settings", on_settings),
            MenuItem(
                "🔄 Start on boot",
                on_boot_toggle,
                checked=lambda item: self.is_start_on_boot_enabled(),
            ),
            Menu.SEPARATOR,
            MenuItem(
                lambda text: f"Status: {'Active' if self._is_active else 'Paused'}",
                None,
                enabled=False,
            ),
            MenuItem(f"v{APP_VERSION}", None, enabled=False),
            Menu.SEPARATOR,
            MenuItem("❌ Quit", on_quit),
        )

        self._tray_icon = pystray.Icon(
            name="desktop_gboard",
            icon=self._create_icon(color=(0, 200, 80)),
            title=APP_NAME,
            menu=menu,
        )

        logger.info("System tray started. Right-click the icon for options.")
        self._tray_icon.run()

    def _create_icon(self, color=(0, 200, 80), size=64):
        """Create a simple colored icon using PIL."""
        from PIL import Image, ImageDraw

        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Draw a rounded rectangle background
        draw.rounded_rectangle(
            [(4, 4), (size - 4, size - 4)],
            radius=12,
            fill=(30, 30, 30, 230),
            outline=color,
            width=3,
        )

        # Draw "G" text
        try:
            from PIL import ImageFont
            font = ImageFont.truetype("segoeui.ttf", size=32)
        except Exception:
            font = ImageFont.load_default()

        draw.text((size // 2, size // 2), "G", fill=color, font=font, anchor="mm")

        return img

    # ─── Console Fallback ────────────────────────────────────────

    def _run_console_fallback(self):
        """Run in console mode when pystray is not available."""
        print(f"╔══════════════════════════════════════╗")
        print(f"║  {APP_NAME} v{APP_VERSION}           ║")
        print(f"║  (Console Mode — no tray icon)       ║")
        print(f"╚══════════════════════════════════════╝")
        print()
        print("Commands: [s]tart  [p]ause  [q]uit")
        print()

        if self._on_start:
            self._on_start()
            self._is_active = True

        while True:
            try:
                cmd = input("> ").strip().lower()
                if cmd in ("q", "quit", "exit"):
                    if self._on_quit:
                        self._on_quit()
                    break
                elif cmd in ("s", "start"):
                    if self._on_start:
                        self._on_start()
                    self._is_active = True
                    print("G-Board started.")
                elif cmd in ("p", "pause", "stop"):
                    if self._on_stop:
                        self._on_stop()
                    self._is_active = False
                    print("G-Board paused.")
                elif cmd == "status":
                    print(f"Active: {self._is_active}")
                else:
                    print("Unknown command. Use: start, pause, quit")
            except (KeyboardInterrupt, EOFError):
                if self._on_quit:
                    self._on_quit()
                break
