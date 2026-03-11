"""
Desktop G-Board — Prediction Suggestion Bar
=============================================
A G-Board-style horizontal suggestion strip that floats near
the text cursor showing 3 word predictions side by side.

Design (matches Google G-Board):
  ┌──────────┬───────────┬──────────┐
  │  word1   │  ★word2★  │  word3   │
  └──────────┴───────────┴──────────┘
   (appears just above the typing cursor)

  - 3 suggestions in a horizontal row
  - Center suggestion = top prediction (bold, brighter)
  - Left/Right = 2nd and 3rd predictions
  - Click any to accept; Tab accepts the center one
  - Thin, compact bar that doesn't block the text below
  - Semi-transparent dark background
"""

import sys
import logging
import threading
from typing import List, Tuple, Optional, Callable

logger = logging.getLogger(__name__)

# ─── Try PySide6 first, then fallback to tkinter ────────────────

_UI_BACKEND = None

try:
    from PySide6.QtWidgets import (
        QApplication, QWidget, QHBoxLayout, QVBoxLayout, QLabel,
        QPushButton, QGraphicsDropShadowEffect, QSizePolicy
    )
    from PySide6.QtCore import Qt, QTimer, Signal, QObject
    from PySide6.QtGui import QColor, QFont, QCursor
    _UI_BACKEND = "pyside6"
    logger.info("UI backend: PySide6 (hardware-accelerated)")
except ImportError:
    _UI_BACKEND = "tkinter"
    logger.info("UI backend: tkinter (fallback)")


# ═══════════════════════════════════════════════════════════════
#  PySide6 G-Board Strip (Primary)
# ═══════════════════════════════════════════════════════════════

if _UI_BACKEND == "pyside6":

    class _Signals(QObject):
        """Thread-safe Qt signals for cross-thread UI updates."""
        update_predictions = Signal(list)
        move_to = Signal(int, int)
        show_overlay = Signal()
        hide_overlay = Signal()
        show_code_result = Signal(str)

    class PredictionOverlay(QWidget):
        """
        G-Board-style horizontal suggestion bar.
        Shows 3 predictions side by side, center = best match.
        """

        STRIP_HEIGHT = 32          # Total bar height in px
        STRIP_WIDTH = 320          # Total bar width in px
        NUM_SUGGESTIONS = 3        # Left | Center | Right

        def __init__(self, on_prediction_selected: Optional[Callable[[str], None]] = None):
            self._app = QApplication.instance()
            if not self._app:
                self._app = QApplication(sys.argv)

            super().__init__()
            self._on_selected = on_prediction_selected
            self._predictions: List[Tuple[str, float]] = []
            self._buttons: List[QPushButton] = []
            self._is_visible = False

            # Thread-safe signals
            self._signals = _Signals()
            self._signals.update_predictions.connect(self._do_update_predictions)
            self._signals.move_to.connect(self._do_move_to)
            self._signals.show_overlay.connect(self._do_show)
            self._signals.hide_overlay.connect(self._do_hide)
            self._signals.show_code_result.connect(self._do_show_code_result)

            self._setup_window()
            self._setup_ui()

        def _setup_window(self):
            """Configure window: frameless, transparent, always-on-top, no focus steal."""
            self.setWindowFlags(
                Qt.WindowStaysOnTopHint |
                Qt.FramelessWindowHint |
                Qt.Tool |
                Qt.WindowDoesNotAcceptFocus
            )
            self.setAttribute(Qt.WA_TranslucentBackground, True)
            self.setAttribute(Qt.WA_ShowWithoutActivating, True)
            self.setFixedSize(self.STRIP_WIDTH, self.STRIP_HEIGHT)

        def _setup_ui(self):
            """Build the G-Board horizontal suggestion strip."""
            # Outer layout
            outer = QVBoxLayout(self)
            outer.setContentsMargins(0, 0, 0, 0)
            outer.setSpacing(0)

            # Container bar
            self._container = QWidget()
            self._container.setObjectName("gbar")
            self._container.setStyleSheet("""
                #gbar {
                    background-color: rgba(38, 38, 38, 235);
                    border: 1px solid rgba(70, 70, 70, 100);
                    border-radius: 16px;
                }
            """)

            # Subtle shadow
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(12)
            shadow.setColor(QColor(0, 0, 0, 100))
            shadow.setOffset(0, 2)
            self._container.setGraphicsEffect(shadow)

            # Horizontal layout for 3 suggestions
            hbox = QHBoxLayout(self._container)
            hbox.setContentsMargins(4, 2, 4, 2)
            hbox.setSpacing(2)

            # Separator style
            sep_style = "background-color: rgba(80, 80, 80, 80); min-width: 1px; max-width: 1px;"

            # Button styles
            side_style = """
                QPushButton {
                    background: transparent;
                    color: rgba(200, 200, 200, 220);
                    border: none;
                    border-radius: 12px;
                    font-family: 'Segoe UI', sans-serif;
                    font-size: 13px;
                    padding: 0 8px;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 25);
                    color: #ffffff;
                }
            """

            center_style = """
                QPushButton {
                    background: transparent;
                    color: #ffffff;
                    border: none;
                    border-radius: 12px;
                    font-family: 'Segoe UI', sans-serif;
                    font-size: 14px;
                    font-weight: bold;
                    padding: 0 10px;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 30);
                }
            """

            # Create 3 buttons: [Left] | [Center] | [Right]
            # _buttons[0]=left, _buttons[1]=center(bold), _buttons[2]=right
            for i in range(self.NUM_SUGGESTIONS):
                btn = QPushButton("")
                btn.setCursor(QCursor(Qt.PointingHandCursor))
                btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                btn.setStyleSheet(center_style if i == 1 else side_style)
                btn.clicked.connect(lambda checked, idx=i: self._on_click(idx))
                btn.setVisible(False)

                if i == 1:
                    # Left separator before center
                    sep_left = QWidget()
                    sep_left.setStyleSheet(sep_style)
                    sep_left.setFixedWidth(1)
                    hbox.addWidget(sep_left)
                    self._sep_left = sep_left

                hbox.addWidget(btn)
                self._buttons.append(btn)

                if i == 1:
                    # Right separator after center
                    sep_right = QWidget()
                    sep_right.setStyleSheet(sep_style)
                    sep_right.setFixedWidth(1)
                    hbox.addWidget(sep_right)
                    self._sep_right = sep_right

            # Code result label (hidden by default)
            self._code_label = QLabel("")
            self._code_label.setWordWrap(True)
            self._code_label.setStyleSheet("""
                QLabel {
                    color: #4ec9b0;
                    font-family: 'Cascadia Code', 'Consolas', monospace;
                    font-size: 11px;
                    padding: 4px 8px;
                    background: transparent;
                }
            """)
            self._code_label.setVisible(False)
            hbox.addWidget(self._code_label)

            outer.addWidget(self._container)

        # ─── Thread-safe Public API ──────────────────────────────

        def update_predictions(self, predictions: List[Tuple[str, float]]):
            """Update predictions (thread-safe)."""
            self._signals.update_predictions.emit(predictions)

        def move_to_caret(self, x: int, y: int):
            """Move overlay to follow caret (thread-safe)."""
            self._signals.move_to.emit(x, y)

        def show_overlay(self):
            self._signals.show_overlay.emit()

        def hide_overlay(self):
            self._signals.hide_overlay.emit()

        def show_code_result(self, text: str):
            self._signals.show_code_result.emit(text)

        def run(self):
            """Start the Qt event loop (must be called from main thread)."""
            self._app.exec()

        # ─── Internal Slot Implementations ───────────────────────

        def _do_update_predictions(self, predictions):
            """
            Map predictions to the G-Board layout:
              predictions[0] → center button (bold, primary)
              predictions[1] → left button
              predictions[2] → right button
            """
            self._predictions = predictions
            self._code_label.setVisible(False)

            if not predictions:
                self._do_hide()
                return

            # Map: center=best, left=2nd, right=3rd
            # _buttons[0]=left, _buttons[1]=center, _buttons[2]=right
            # predictions[0]=best → center, predictions[1] → left, predictions[2] → right
            mapping = {0: 1, 1: 0, 2: 2}  # pred_idx → btn_idx
            # So: btn 0(left) gets pred 1, btn 1(center) gets pred 0, btn 2(right) gets pred 2

            for btn_idx in range(self.NUM_SUGGESTIONS):
                btn = self._buttons[btn_idx]
                # Which prediction goes in this button?
                if btn_idx == 0:
                    pred_idx = 1   # left  ← 2nd prediction
                elif btn_idx == 1:
                    pred_idx = 0   # center ← best prediction
                else:
                    pred_idx = 2   # right ← 3rd prediction

                if pred_idx < len(predictions):
                    word, _ = predictions[pred_idx]
                    btn.setText(word)
                    btn.setVisible(True)
                else:
                    btn.setText("")
                    btn.setVisible(False)

            # Show/hide separators based on visible buttons
            has_left = self._buttons[0].isVisible()
            has_right = self._buttons[2].isVisible()
            self._sep_left.setVisible(has_left)
            self._sep_right.setVisible(has_right)

            self.adjustSize()
            self._do_show()

        def _do_move_to(self, x, y):
            """Position the bar ABOVE the caret, centered on it."""
            screen = self._app.primaryScreen().geometry()
            bar_w = self.width()
            bar_h = self.height()

            # Center horizontally on the caret
            overlay_x = x - bar_w // 2
            # Place ABOVE the caret with a small gap
            overlay_y = y - bar_h - 6

            # If above goes off-screen, place below caret instead
            if overlay_y < 0:
                overlay_y = y + 24

            # Keep within horizontal screen bounds
            if overlay_x < 4:
                overlay_x = 4
            if overlay_x + bar_w > screen.width() - 4:
                overlay_x = screen.width() - bar_w - 4

            self.move(overlay_x, overlay_y)

        def _do_show(self):
            if not self._is_visible:
                self.show()
                self._is_visible = True

        def _do_hide(self):
            if self._is_visible:
                self.hide()
                self._is_visible = False

        def _do_show_code_result(self, text):
            """Show code completion result in the bar."""
            for btn in self._buttons:
                btn.setVisible(False)
            self._sep_left.setVisible(False)
            self._sep_right.setVisible(False)
            self._code_label.setText(text[:200])
            self._code_label.setVisible(True)
            self.adjustSize()
            self._do_show()
            QTimer.singleShot(10000, lambda: self._code_label.setVisible(False))

        def _on_click(self, btn_idx):
            """Handle click on a suggestion button."""
            # Map button index back to prediction index
            pred_map = {0: 1, 1: 0, 2: 2}
            pred_idx = pred_map[btn_idx]
            if pred_idx < len(self._predictions):
                word, _ = self._predictions[pred_idx]
                if self._on_selected:
                    self._on_selected(word)
                self._do_hide()


# ═══════════════════════════════════════════════════════════════
#  Tkinter G-Board Strip (Fallback)
# ═══════════════════════════════════════════════════════════════

elif _UI_BACKEND == "tkinter":

    class PredictionOverlay:
        """
        G-Board-style suggestion bar using tkinter.
        3 horizontal predictions, center = best.
        """

        def __init__(self, on_prediction_selected: Optional[Callable[[str], None]] = None):
            import tkinter as tk

            self._tk = tk
            self._on_selected = on_prediction_selected
            self._predictions: List[Tuple[str, float]] = []
            self._root = tk.Tk()
            self._root.withdraw()

            # Window: frameless, topmost, semi-transparent
            self._root.overrideredirect(True)
            self._root.attributes("-topmost", True)
            self._root.attributes("-alpha", 0.93)
            self._root.configure(bg="#262626")

            # Horizontal frame for 3 suggestion buttons
            self._frame = tk.Frame(self._root, bg="#262626")
            self._frame.pack(fill="x", padx=2, pady=2)

            self._labels: List[tk.Label] = []

            # Create 3 labels: [left=2nd] | [center=1st] | [right=3rd]
            for i in range(3):
                is_center = (i == 1)
                label = tk.Label(
                    self._frame,
                    text="",
                    bg="#262626",
                    fg="#ffffff" if is_center else "#c8c8c8",
                    font=("Segoe UI", 11, "bold") if is_center else ("Segoe UI", 10),
                    anchor="center",
                    padx=12,
                    pady=4,
                    cursor="hand2",
                )
                label.pack(side="left", fill="both", expand=True)
                label.bind("<Button-1>", lambda e, idx=i: self._on_click(idx))
                self._labels.append(label)

                # Add separator after left and center
                if i < 2:
                    sep = tk.Frame(self._frame, bg="#505050", width=1)
                    sep.pack(side="left", fill="y", padx=0, pady=4)

            self._is_visible = False

        def update_predictions(self, predictions: List[Tuple[str, float]]):
            """Map predictions: center=best, left=2nd, right=3rd."""
            self._predictions = predictions

            if not predictions:
                self.hide_overlay()
                return

            # label[0]=left←pred[1], label[1]=center←pred[0], label[2]=right←pred[2]
            label_to_pred = {0: 1, 1: 0, 2: 2}
            for lbl_idx, pred_idx in label_to_pred.items():
                if pred_idx < len(predictions):
                    word, _ = predictions[pred_idx]
                    self._labels[lbl_idx].configure(text=word)
                else:
                    self._labels[lbl_idx].configure(text="")

            self.show_overlay()

        def move_to_caret(self, x: int, y: int):
            """Position above the caret, centered."""
            bar_w = 320
            bar_h = 32
            ox = max(4, x - bar_w // 2)
            oy = y - bar_h - 6
            if oy < 0:
                oy = y + 24
            self._root.geometry(f"{bar_w}x{bar_h}+{ox}+{oy}")

        def show_overlay(self):
            if not self._is_visible:
                self._root.deiconify()
                self._is_visible = True

        def hide_overlay(self):
            if self._is_visible:
                self._root.withdraw()
                self._is_visible = False

        def show_code_result(self, text: str):
            """Show code result in the center label."""
            for lbl in self._labels:
                lbl.configure(text="")
            self._labels[1].configure(text=text[:60])
            self.show_overlay()

        def run(self):
            self._root.mainloop()

        def _on_click(self, lbl_idx):
            """Map label click back to prediction index."""
            pred_map = {0: 1, 1: 0, 2: 2}
            pred_idx = pred_map[lbl_idx]
            if pred_idx < len(self._predictions):
                word, _ = self._predictions[pred_idx]
                if self._on_selected:
                    self._on_selected(word)
                self.hide_overlay()
