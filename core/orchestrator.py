"""
Desktop G-Board — Main Orchestrator
=====================================
The central coordination loop that connects:
  Keystroke Hook → Context Manager → Inference Engine → UI Overlay

This is the "brain" of the system. It:
  1. Receives key events from the HookBridge
  2. Maintains typing context per-window via ContextManager
  3. Routes inference requests via HybridInferenceEngine
  4. Updates the PredictionOverlay with results
  5. Handles hotkeys for Code Assist / Elaborate
  6. Manages autocorrection and text injection

Architecture:
  ┌─────────────┐    ┌──────────────┐    ┌──────────────────┐
  │  HookBridge │───→│ Orchestrator │───→│ InferenceEngine  │
  │ (C++ / py)  │    │  (this file) │    │ (local + cloud)  │
  └─────────────┘    └──────┬───────┘    └──────────────────┘
                            │
              ┌─────────────┼─────────────┐
              │             │             │
     ┌────────▼──┐  ┌───────▼───┐  ┌──────▼──────┐
     │  Context  │  │   Caret   │  │  Process    │
     │  Manager  │  │  Tracker  │  │  Detector   │
     └───────────┘  └───────────┘  └─────────────┘
"""

import os
import sys
import time
import threading
import logging
import pickle
from typing import Optional, Callable, List, Tuple
from pynput import keyboard as pynput_keyboard

# Core modules
from core.hook_bridge import HookBridge, KeyEvent, VK
from core.context_manager import ContextManager
from core.caret_tracker import CaretTracker, CaretPollingThread
from core.process_detector import ProcessMonitor, ActiveWindowInfo

# Inference
from inference.engine import HybridInferenceEngine
from inference.decision_logic import InferenceRequest, RequestType, InferenceResult

# Existing AI modules
from src.autocorrect import AutoCorrector, Dictionary
from src.prediction import WordPredictor
from src.user_model import UserProfile, UserLearner

logger = logging.getLogger(__name__)


# ─── Hotkey Configuration ────────────────────────────────────────
HOTKEY_CODE_ASSIST = (VK.CTRL, 0x4A)    # Ctrl+J  → Code Assist
HOTKEY_ELABORATE   = (VK.CTRL, 0x45)    # Ctrl+E  → Elaborate
HOTKEY_DISMISS     = (VK.ESCAPE,)       # Esc     → Dismiss overlay


class Orchestrator:
    """
    Main orchestration loop for Desktop G-Board.

    Lifecycle:
      1. initialize() → Load dictionary, models, start subsystems
      2. start()      → Begin capturing keystrokes
      3. [running]    → Process keys, run inference, update UI
      4. stop()       → Clean shutdown
    """

    def __init__(self, config: dict = None):
        self._config = config or {}
        self._is_running = False
        self._is_simulating = False  # Flag to ignore our own injected keys
        self._sim_timer: Optional[threading.Timer] = None  # Timer to clear simulation flag

        # ─── Subsystems ──────────────────────────────────────────
        self.hook_bridge: Optional[HookBridge] = None
        self.context_manager = ContextManager()
        self.caret_tracker = CaretTracker()
        self.caret_poller: Optional[CaretPollingThread] = None
        self.process_monitor = ProcessMonitor()
        self.inference_engine = HybridInferenceEngine(
            config=self._config.get("inference", {})
        )

        # ─── AI Components (from existing codebase) ─────────────
        self.dictionary: Optional[Dictionary] = None
        self.predictor: Optional[WordPredictor] = None
        self.corrector: Optional[AutoCorrector] = None
        self.learner: Optional[UserLearner] = None

        # ─── Keyboard Controller (for text injection) ───────────
        self.kb_controller = pynput_keyboard.Controller()

        # ─── Callbacks (for UI) ─────────────────────────────────
        self._on_predictions_updated: Optional[Callable] = None
        self._on_correction_made: Optional[Callable] = None
        self._on_code_result: Optional[Callable] = None
        self._on_caret_moved: Optional[Callable] = None

        # ─── Last known caret position ──────────────────────────
        self._last_caret_x: int = 0
        self._last_caret_y: int = 0

        # ─── Current predictions (for auto-complete on space) ────
        self._predictions: List[Tuple[str, float]] = []

        # ─── Undo correction (backspace after auto-correct reverts) ──
        self._last_correction: Optional[Tuple[str, str, str]] = None  # (original, corrected, separator)

        # ─── Hotkey State ────────────────────────────────────────
        self._modifier_state = {VK.CTRL: False, VK.SHIFT: False, VK.ALT: False}

    # ─── Lifecycle ───────────────────────────────────────────────

    def initialize(self):
        """Load dictionary, AI models, and prepare all subsystems."""
        logger.info("Initializing Desktop G-Board orchestrator...")

        # 1. Load dictionary
        self.dictionary = Dictionary()
        dict_path = os.path.join("data", "dictionaries", "english.txt")
        if os.path.exists(dict_path):
            self.dictionary.load_from_file(dict_path)
            logger.info("Loaded dictionary: %d words", len(self.dictionary))
        else:
            logger.warning("Dictionary not found at %s — using default (~120 words)", dict_path)

        # Add common abbreviations
        for word in ["r", "u", "ur", "ok", "idk", "omw", "brb", "lol", "thx"]:
            self.dictionary.add_word(word, 100)

        # 2. Set up predictor with pre-trained model if available
        self.predictor = WordPredictor(n=3)
        model_path = os.path.join("data", "models", "world_model.pkl")
        if os.path.exists(model_path):
            try:
                with open(model_path, "rb") as f:
                    self.predictor.model = pickle.load(f)
                logger.info("Loaded pre-trained n-gram model.")
            except Exception as e:
                logger.warning("Could not load world model: %s", e)

        # 3. Set up autocorrector
        self.corrector = AutoCorrector(
            dictionary=self.dictionary,
            max_edit_distance=2,
            ngram_model=self.predictor.model,
        )

        # 4. Set up user learner
        profile = UserProfile(user_id="desktop_user")
        profile_path = os.path.join("data", "user_data")
        if os.path.exists(os.path.join(profile_path, "desktop_user.json")):
            profile = UserProfile.load("desktop_user", directory=profile_path)
            logger.info("Loaded user profile: %d custom words", len(profile.custom_words))
        self.learner = UserLearner(profile=profile, dictionary=self.dictionary)

        # 5. Initialize inference engine with our AI components
        self.inference_engine.initialize(
            dictionary=self.dictionary,
            ngram_model=self.predictor.model,
            autocorrector=self.corrector,
        )

        # 6. Set up hook bridge
        hook_mode = self._config.get("hook_mode", "fallback")
        self.hook_bridge = HookBridge(mode=hook_mode)

        logger.info("Orchestrator initialized successfully.")

    def start(self):
        """Start all subsystems and begin processing keystrokes."""
        if self._is_running:
            logger.warning("Orchestrator is already running.")
            return

        self._is_running = True

        # Start process monitor
        self.process_monitor.start(callback=self._on_window_changed)

        # Start caret poller
        self.caret_poller = CaretPollingThread(self.caret_tracker, interval_ms=50)
        self.caret_poller.start(callback=self._on_caret_position_changed)

        # Start keyboard hook
        self.hook_bridge.start(callback=self._on_key_event)

        logger.info("Desktop G-Board is now active. Capturing keystrokes...")

    def stop(self):
        """Stop all subsystems gracefully."""
        logger.info("Stopping Desktop G-Board...")
        self._is_running = False

        if self.hook_bridge:
            self.hook_bridge.stop()
        if self.caret_poller:
            self.caret_poller.stop()
        self.process_monitor.stop()

        # Save user profile
        if self.learner:
            self.learner.save()
            logger.info("User profile saved.")

        logger.info("Desktop G-Board stopped.")

    # ─── UI Callbacks Registration ───────────────────────────────

    def set_callbacks(self,
                      on_predictions: Callable = None,
                      on_correction: Callable = None,
                      on_code_result: Callable = None,
                      on_caret_moved: Callable = None):
        """Register UI callbacks."""
        self._on_predictions_updated = on_predictions
        self._on_correction_made = on_correction
        self._on_code_result = on_code_result
        self._on_caret_moved = on_caret_moved

    # ─── Key Event Processing ────────────────────────────────────

    def _on_key_event(self, event: KeyEvent):
        """
        Main key event handler — called for every keystroke.
        Routes to the appropriate handler based on key type.
        """
        if self._is_simulating:
            return  # Ignore our own injected keystrokes

        if not event.is_keydown:
            # Track modifier releases
            if event.vk_code in (VK.CTRL, VK.SHIFT, VK.ALT):
                self._modifier_state[event.vk_code] = False
            return

        # Track modifier presses
        if event.vk_code in (VK.CTRL, VK.SHIFT, VK.ALT):
            self._modifier_state[event.vk_code] = True
            return

        # Check for hotkeys
        if self._check_hotkeys(event):
            return

        # ─── Regular Key Processing ─────────────────────────
        if event.is_char and (event.character.isalnum() or event.character == "'"):
            # Character key — add to context buffer
            self.context_manager.on_character(event.character)
            self._last_correction = None  # Typing clears undo
            self._update_predictions()

        elif event.is_space or event.is_enter:
            # Word boundary — trigger autocorrect + update predictions
            separator = " " if event.is_space else "\n"
            self._handle_word_boundary(separator)

        elif event.is_backspace:
            # ─ Undo correction: backspace right after auto-correct reverts it
            if self._last_correction:
                original, corrected, sep = self._last_correction
                self._last_correction = None
                logger.info("Undo correction: '%s' → '%s' (reverted)", corrected, original)
                self._undo_correction(original, corrected, sep)
                return

            self._last_correction = None  # Any other backspace clears undo
            self.context_manager.on_backspace()
            self._update_predictions()

        elif event.is_word_boundary:
            # Punctuation — treat as word boundary
            self._handle_word_boundary(event.character)

    def _check_hotkeys(self, event: KeyEvent) -> bool:
        """Check if the key event triggers a hotkey. Returns True if consumed."""
        ctrl = self._modifier_state.get(VK.CTRL, False)

        # Ctrl+J → Code Assist
        if ctrl and event.vk_code == 0x4A:
            self._trigger_code_assist()
            return True

        # Ctrl+E → Elaborate
        if ctrl and event.vk_code == 0x45:
            self._trigger_elaborate()
            return True

        # Escape → Dismiss
        if event.vk_code == VK.ESCAPE:
            if self._on_predictions_updated:
                self._on_predictions_updated([])
            return True

        return False

    # ─── Word Processing ─────────────────────────────────────────

    def _handle_word_boundary(self, separator: str):
        """
        Process a completed word on space/enter/punctuation.

        G-Board behavior:
          1. If the top prediction starts with what the user typed,
             auto-complete it (type "hel " → inserts "hello ")
          2. If the word is misspelled, auto-correct it
          3. Learn from the final word
          4. Update next-word predictions
        """
        word = self.context_manager.get_current_word()

        if word:
            final_word = word
            context = self.context_manager.get_ngram_context()
            sentence = self.context_manager.get_sentence_context()

            # ── Step 1: Auto-complete from prediction ────────────
            # Only auto-complete if:
            #   a) The typed text is NOT already a valid dictionary word
            #   b) The top prediction starts with what the user typed
            #   c) Confidence is high enough
            # This prevents "the" → "there", "he" → "hello", etc.
            auto_completed = False
            if self._predictions and len(word) >= 2:
                top_word, top_score = self._predictions[0]
                word_is_valid = (self.dictionary and
                                 self.dictionary.contains(word.lower()))
                if (not word_is_valid
                        and top_word.lower().startswith(word.lower())
                        and top_word.lower() != word.lower()
                        and top_score > 0.5):  # Higher confidence threshold
                    logger.info("Auto-complete: '%s' → '%s' (score=%.2f)",
                               word, top_word, top_score)
                    self._replace_word(word, top_word, separator)
                    # Sync context: replace the old word with the new one
                    for _ in range(len(word)):
                        self.context_manager.on_backspace()
                    self.context_manager.on_character(top_word)
                    self._last_correction = (word, top_word, separator)  # Enable undo
                    if self._on_correction_made:
                        self._on_correction_made(word, top_word)
                    final_word = top_word
                    auto_completed = True

            # ── Step 2: Autocorrect misspelled words ─────────────
            # Only if we didn't already auto-complete
            if not auto_completed:
                request = InferenceRequest(
                    request_type=RequestType.AUTOCORRECT,
                    context=context,
                    current_word=word,
                    context_mode=self.process_monitor.current_mode,
                )
                result = self.inference_engine.infer(request)

                corrected = word
                if result.predictions:
                    corrected = result.predictions[0][0]

                if corrected.lower() != word.lower():
                    logger.info("Autocorrect: '%s' → '%s'", word, corrected)
                    self._replace_word(word, corrected, separator)
                    # Sync context: replace the old word with the new one
                    for _ in range(len(word)):
                        self.context_manager.on_backspace()
                    self.context_manager.on_character(corrected)
                    self._last_correction = (word, corrected, separator)  # Enable undo
                    if self._on_correction_made:
                        self._on_correction_made(word, corrected)
                    final_word = corrected

            # ── Step 3: Learn from the final word ────────────────
            if self.learner:
                self.learner.learn_from_text(final_word)
            if self.predictor:
                self.predictor.train(final_word)

        # 4. Record the separator in context
        self.context_manager.on_character(separator)

        # 5. Clear current predictions (word is done)
        self._predictions = []

        # 6. Update predictions for what comes next
        self._update_predictions()

    def _update_predictions(self):
        """
        Get fresh predictions — context-aware word completion + next-word.

        Uses the full sentence context (not just last N words) so predictions
        understand what the user is writing about:
          "I am go" → "going" (not just any word starting with "go")
          "the weather is b" → "beautiful", "bad"
        """
        current_word = self.context_manager.get_current_word()
        ngram_context = self.context_manager.get_ngram_context()
        sentence_context = self.context_manager.get_sentence_context()

        predictions = []

        # 1. Word completion: if user is mid-word (2+ chars), show completions
        #    Uses sentence context for smarter ranking
        if current_word and len(current_word) >= 2:
            # Fast local completion (n-gram + dictionary, <10ms)
            completions = self.inference_engine.local.complete_word(
                prefix=current_word,
                context=ngram_context,
                sentence=sentence_context,
                top_k=3,
            )
            if completions:
                predictions = completions

            # If local gives weak results and cloud is available,
            # fire a cloud completion in background (arrives ~200ms later)
            if len(predictions) < 3 and self.inference_engine.cloud.is_available:
                self._request_cloud_completion(sentence_context, current_word)

        # 2. Next-word prediction: at a word boundary (after space)
        if not predictions:
            effective_context = sentence_context or ngram_context
            if not effective_context.strip():
                if self._on_predictions_updated:
                    self._on_predictions_updated([])
                return

            request = InferenceRequest(
                request_type=RequestType.NEXT_WORD,
                context=effective_context,
                current_word=current_word,
                context_mode=self.process_monitor.current_mode,
                top_k=3,
            )
            result = self.inference_engine.infer(request)
            predictions = result.predictions

        if self._on_predictions_updated:
            self._pin_overlay_to_caret()
            self._predictions = predictions  # Cache for auto-complete on space
            self._on_predictions_updated(predictions)

    def _request_cloud_completion(self, sentence: str, prefix: str):
        """Fire an async cloud word-completion request to enrich predictions."""
        import threading

        def _cloud_worker():
            try:
                cloud_preds = self.inference_engine.cloud.complete_word_in_context(
                    sentence=sentence,
                    prefix=prefix,
                    top_k=3,
                )
                if cloud_preds and self._on_predictions_updated:
                    # Merge: cloud results are high quality
                    self._pin_overlay_to_caret()
                    self._predictions = cloud_preds  # Update cache
                    self._on_predictions_updated(cloud_preds)
            except Exception as e:
                logger.debug("Cloud completion failed: %s", e)

        thread = threading.Thread(target=_cloud_worker, daemon=True, name="CloudComplete")
        thread.start()

    # ─── Special Actions ─────────────────────────────────────────

    def _trigger_code_assist(self):
        """Handle Ctrl+J → Code Assist hotkey."""
        logger.info("Code Assist triggered (mode=%s)", self.process_monitor.current_mode)

        context = self.context_manager.get_full_context()
        request = InferenceRequest(
            request_type=RequestType.CODE_ASSIST,
            context=context,
            context_mode=self.process_monitor.current_mode,
            process_name=self.process_monitor.current_info.process_name
                         if self.process_monitor.current_info else "",
            max_latency_ms=5000,  # Cloud calls can take longer
        )

        # Run async so the keyboard doesn't freeze
        def on_result(result: InferenceResult):
            if result.raw_text and self._on_code_result:
                self._on_code_result(result.raw_text)
            elif result.error:
                logger.error("Code Assist failed: %s", result.error)

        self.inference_engine.infer_async(request, callback=on_result)

    def _trigger_elaborate(self):
        """Handle Ctrl+E → Elaborate hotkey."""
        logger.info("Elaborate triggered")

        context = self.context_manager.get_context(max_chars=500)
        request = InferenceRequest(
            request_type=RequestType.ELABORATE,
            context=context,
            context_mode=self.process_monitor.current_mode,
            max_latency_ms=10000,
        )

        def on_result(result: InferenceResult):
            if result.raw_text and self._on_code_result:
                self._on_code_result(result.raw_text)

        self.inference_engine.infer_async(request, callback=on_result)

    # ─── Text Injection ──────────────────────────────────────────

    def accept_prediction(self, word: str):
        """Insert a predicted word into the active application."""
        self._begin_simulating()
        try:
            # Delete the partial word being typed
            current = self.context_manager.get_current_word()
            for _ in range(len(current)):
                self.kb_controller.press(pynput_keyboard.Key.backspace)
                self.kb_controller.release(pynput_keyboard.Key.backspace)
                time.sleep(0.01)

            # Type the prediction + space
            self.kb_controller.type(word + " ")

            # Update context: remove partial word, then add full word + space
            for _ in range(len(current)):
                self.context_manager.on_backspace()
            self.context_manager.on_character(word + " ")

            # Learn
            if self.learner:
                self.learner.learn_from_text(word)

        finally:
            self._end_simulating()

    def _begin_simulating(self):
        """Mark that we're simulating keystrokes."""
        if self._sim_timer:
            self._sim_timer.cancel()
        self._is_simulating = True

    def _end_simulating(self, delay: float = 0.08):
        """
        Schedule clearing the simulation flag after a delay.

        We can't clear _is_simulating immediately because the injected
        keystroke events are queued in the Windows input stream and
        processed by the pynput listener thread AFTER the current hook
        callback returns. If we clear the flag now, those injected events
        would be processed as real user input — causing cascading
        corrections, context corruption, and random word replacements.
        """
        if self._sim_timer:
            self._sim_timer.cancel()
        self._sim_timer = threading.Timer(delay, self._clear_simulating)
        self._sim_timer.daemon = True
        self._sim_timer.start()

    def _clear_simulating(self):
        """Clear the simulation flag (called from timer thread)."""
        self._is_simulating = False

    def _replace_word(self, original: str, replacement: str, separator: str):
        """Delete a typed word and replace it with the correction."""
        self._begin_simulating()
        try:
            # Backspace the separator (already typed by user into the app)
            self.kb_controller.press(pynput_keyboard.Key.backspace)
            self.kb_controller.release(pynput_keyboard.Key.backspace)

            # Backspace the original word
            for _ in range(len(original)):
                self.kb_controller.press(pynput_keyboard.Key.backspace)
                self.kb_controller.release(pynput_keyboard.Key.backspace)
                time.sleep(0.01)

            # Type the replacement + separator
            self.kb_controller.type(replacement + separator)
        finally:
            self._end_simulating()

    def _undo_correction(self, original: str, corrected: str, separator: str):
        """
        Undo a recent auto-correction or auto-completion.
        Called when user presses backspace immediately after a correction.

        Replaces "corrected + separator" with "original + separator"
        so the user gets back exactly what they typed.
        """
        self._begin_simulating()
        try:
            # NOTE: The user's backspace key already removed the separator
            # from the app (the backspace was processed by the OS before our
            # hook callback ran). So we only need to remove the corrected word.

            # Remove the corrected word
            for _ in range(len(corrected)):
                self.kb_controller.press(pynput_keyboard.Key.backspace)
                self.kb_controller.release(pynput_keyboard.Key.backspace)
                time.sleep(0.01)

            # Re-type the original word + separator
            self.kb_controller.type(original + separator)

            # Update context to reflect the original word
            # (context still has corrected + separator since the backspace
            #  that triggered undo did NOT update context_manager)
            for _ in range(len(corrected) + len(separator)):
                self.context_manager.on_backspace()
            self.context_manager.on_character(original + separator)

            logger.info("Correction undone: '%s' → '%s'", corrected, original)
        finally:
            self._end_simulating()

    # ─── Event Handlers ──────────────────────────────────────────

    def _on_window_changed(self, info: ActiveWindowInfo):
        """Handle active window change."""
        window_id = str(info.hwnd)
        self.context_manager.set_active_window(
            window_id=window_id,
            title=info.window_title,
            process=info.process_name,
        )
        logger.debug("Window changed: [%s] %s (mode=%s)",
                    info.process_name, info.window_title[:40], info.context_mode)

    def _on_caret_position_changed(self, pos):
        """Handle caret movement — cache position and update overlay."""
        if pos.is_valid:
            self._last_caret_x = pos.x
            self._last_caret_y = pos.y
        if self._on_caret_moved:
            self._on_caret_moved(pos.x, pos.y)

    def _pin_overlay_to_caret(self):
        """Move the overlay to the last known caret position."""
        if self._on_caret_moved and (self._last_caret_x or self._last_caret_y):
            self._on_caret_moved(self._last_caret_x, self._last_caret_y)
        else:
            # No cached position — do a fresh caret lookup
            pos = self.caret_tracker.get_caret_position()
            if pos.is_valid:
                self._last_caret_x = pos.x
                self._last_caret_y = pos.y
                if self._on_caret_moved:
                    self._on_caret_moved(pos.x, pos.y)
