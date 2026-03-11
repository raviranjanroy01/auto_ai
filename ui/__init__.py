"""
Desktop G-Board — UI Module
==============================
Transparent overlay + system tray integration.
"""

from .overlay import PredictionOverlay
from .system_tray import SystemTrayApp

__all__ = ["PredictionOverlay", "SystemTrayApp"]
