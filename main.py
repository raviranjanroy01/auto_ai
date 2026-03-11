"""
Desktop G-Board — Main Entry Point
====================================
Launch the global text prediction, autocorrect, and AI code
assistance service as a system tray application.

Usage:
    python main.py                  # Normal launch (system tray + overlay)
    python main.py --console        # Console mode (no tray icon)
    python main.py --hook native    # Use C++ hook service (requires build)
    python main.py --offline        # Offline mode (no cloud API calls)
"""

import sys
import os
import logging
import argparse
import threading

# Ensure project root is in path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "src"))

from config.settings import Config
from core.orchestrator import Orchestrator
from ui.overlay import PredictionOverlay
from ui.system_tray import SystemTrayApp


def setup_logging(level: str = "INFO"):
    """Configure logging for the application."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(name)-20s] %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    # Quiet down noisy loggers
    logging.getLogger("comtypes").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)


def main():
    parser = argparse.ArgumentParser(description="Desktop G-Board — Global AI Typing Assistant")
    parser.add_argument("--console", action="store_true", help="Run in console mode (no tray)")
    parser.add_argument("--hook", choices=["native", "fallback"], default=None,
                       help="Hook mode: 'native' (C++ service) or 'fallback' (pynput)")
    parser.add_argument("--offline", action="store_true", help="Disable cloud API calls")
    parser.add_argument("--config", type=str, default=None, help="Path to config.yaml")
    args = parser.parse_args()

    # ─── Load Configuration ──────────────────────────────────
    config = Config(config_path=args.config)

    if args.hook:
        config.set("general", "hook_mode", args.hook)
    if args.offline:
        config.set("inference", "offline_only", True)

    setup_logging(config.get("general", "log_level", "INFO"))
    logger = logging.getLogger("main")

    logger.info("=" * 50)
    logger.info("  Desktop G-Board v%s", config.get("general", "version"))
    logger.info("=" * 50)

    # ─── Initialize Orchestrator ─────────────────────────────
    orchestrator = Orchestrator(config=config.as_dict())
    orchestrator.initialize()

    # ─── Initialize UI Overlay ───────────────────────────────
    overlay = PredictionOverlay(
        on_prediction_selected=orchestrator.accept_prediction
    )

    # ─── Wire up callbacks ───────────────────────────────────
    orchestrator.set_callbacks(
        on_predictions=overlay.update_predictions,
        on_correction=lambda orig, fix: logger.info("Corrected: %s -> %s", orig, fix),
        on_code_result=overlay.show_code_result,
        on_caret_moved=overlay.move_to_caret,
    )

    # ─── System Tray ─────────────────────────────────────────
    tray = SystemTrayApp(
        on_start=orchestrator.start,
        on_stop=orchestrator.stop,
        on_quit=lambda: (orchestrator.stop(), sys.exit(0)),
    )

    # Start orchestrator
    orchestrator.start()
    tray.set_active(True)

    if args.console:
        # Console mode — run tray in console fallback
        tray._use_pystray = False
        tray.run()
    else:
        # Start tray in a background thread, run overlay on main thread
        tray_thread = threading.Thread(target=tray.run, daemon=True, name="SystemTray")
        tray_thread.start()

        # Qt/tkinter event loop must run on main thread
        try:
            overlay.run()
        except KeyboardInterrupt:
            orchestrator.stop()


if __name__ == "__main__":
    main()
