"""
AutoAI Desktop Service
======================
The background engine that connects the keyboard listener to the AI models.
Handles:
  - System-wide keystroke capturing
  - Live buffer management
  - Triggering corrections and predictions
  - Sending text back to the system
"""

import threading
import time
from typing import Callable, List, Optional
from pynput import keyboard
import pyperclip
import os
import sys

# ─── Terminal Colors ───
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"

def colored(text, color):
    return f"{color}{text}{Colors.RESET}"

from autocorrect import AutoCorrector, Dictionary
from prediction import WordPredictor
from user_model import UserProfile, UserLearner

class DesktopAssistantService:
    def __init__(self, 
                 on_predictions_updated: Optional[Callable[[List[tuple]], None]] = None,
                 on_correction_made: Optional[Callable[[str, str], None]] = None):
        
        # ─── AI Engine Setup ───
        self.dictionary = Dictionary()
        dict_path = os.path.join('data', 'dictionaries', 'english.txt')
        if os.path.exists(dict_path):
            self.dictionary.load_from_file(dict_path)
            # Standard overrides
            for word in ['r', 'u', 'ur', 'ok', 'idk', 'omw', 'brb', 'lol', 'thx']:
                self.dictionary.add_word(word, 100)

        self.corrector = AutoCorrector(dictionary=self.dictionary, max_edit_distance=2)
        self.predictor = WordPredictor(n=3)
        self.learner = UserLearner(UserProfile(user_id="desktop_user"), dictionary=self.dictionary)

        # ─── State Management ───
        self.buffer = ""            # Current word being typed
        self.full_context = ""      # Last few words for prediction
        self.kb_controller = keyboard.Controller()
        self.is_running = False
        
        # ─── Callbacks ───
        self.on_predictions_updated = on_predictions_updated
        self.on_correction_made = on_correction_made

        # ─── Multi-threading ───
        self.listener_thread = None

    def start(self):
        """Start the background keyboard listener."""
        self.is_running = True
        self.listener_thread = keyboard.Listener(on_press=self._on_press)
        self.listener_thread.start()
        print(f" {colored('🚀', Colors.GREEN)} AutoAI Service Started...")

    def stop(self):
        """Stop the service."""
        self.is_running = False
        if self.listener_thread:
            self.listener_thread.stop()

    def _on_press(self, key):
        """Handle individual keystrokes."""
        try:
            if hasattr(key, 'char') and key.char:
                char = key.char
                if char.isalnum() or char in "'":
                    self.buffer += char
                    # Print current buffer for visibility
                    print(f" {colored('⌨', Colors.CYAN)} Typing: {colored(self.buffer, Colors.WHITE)}", end='\r')
                    self._update_predictions()
                else:
                    self._handle_word_boundary(char)
            
            elif key == keyboard.Key.space:
                self._handle_word_boundary(" ")
            
            elif key == keyboard.Key.backspace:
                if len(self.buffer) > 0:
                    self.buffer = self.buffer[:-1]
                    print(f" {colored('⌨', Colors.CYAN)} Typing: {colored(self.buffer, Colors.WHITE)} ", end='\r')
                    self._update_predictions()
                elif len(self.full_context) > 0:
                    self.full_context = self.full_context[:-1]

            elif key == keyboard.Key.enter:
                print(f"\n {colored('⏎', Colors.GRAY)} Enter pressed.")
                self._handle_word_boundary("\n")

        except Exception as e:
            print(f"Error in listener: {e}")

    def _handle_word_boundary(self, separator: str):
        """Process a word once a separator (space, punctuation) is hit."""
        word = self.buffer.strip()
        
        if word:
            # 1. Check for Auto-correction
            corrected = self.corrector.correct(word)
            
            if corrected.lower() != word.lower():
                print(f"\n {colored('✨', Colors.YELLOW)} Correcting: {colored(word, Colors.RED)} -> {colored(corrected, Colors.GREEN)}")
                self._perform_backspace_replace(word, corrected)
                if self.on_correction_made:
                    self.on_correction_made(word, corrected)
                word = corrected
            
            # 2. Learn from the word
            self.learner.learn_from_text(word)
            self.predictor.train(word)
            
            # 3. Update context
            self.full_context += word + separator
            print(f"\n {colored('📖', Colors.BLUE)} Context: {colored(self.full_context, Colors.GRAY)}")
        else:
            self.full_context += separator

        # 4. Reset buffer
        self.buffer = ""
        self._update_predictions()

    def _update_predictions(self):
        """Fetch new predictions based on current context."""
        context = self.full_context + self.buffer
        preds = self.predictor.predict_next(context, top_k=5)
        if preds:
            p_str = ", ".join([w for w, _ in preds])
            print(f" {colored('🔮', Colors.MAGENTA)} Predictions: {colored(p_str, Colors.GRAY)}     ", end='\r')
        
        if self.on_predictions_updated:
            self.on_predictions_updated(preds)

    def _perform_backspace_replace(self, original: str, new_word: str):
        """Delete wrong word using simulated backspaces and type the correct one."""
        # Simple backspace logic
        for _ in range(len(original)):
            self.kb_controller.press(keyboard.Key.backspace)
            self.kb_controller.release(keyboard.Key.backspace)
        
        self.kb_controller.type(new_word)

    def accept_prediction(self, word: str):
        """Insert a predicted word into the active application."""
        # Add a space if we're not starting a new word
        insertion = word + " "
        self.kb_controller.type(insertion)
        
        # Update our internal state
        self.full_context += insertion
        self.buffer = ""
        self._update_predictions()

if __name__ == "__main__":
    # Test debug run
    def debug_preds(p): pass # Already printing in _update_predictions
    def debug_corr(o, c): pass
    
    service = DesktopAssistantService(on_predictions_updated=debug_preds, on_correction_made=debug_corr)
    service.start()
    
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        service.stop()
