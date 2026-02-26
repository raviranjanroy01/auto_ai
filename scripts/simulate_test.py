"""
AutoAI — Automated Integration Test
==================================
Simulates physical typing to test the desktop assistant's 
auto-correction and prediction logic system-wide.
"""

import time
import os
import sys
from pynput.keyboard import Key, Controller

# Ensure path is set
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

def simulate_typing():
    keyboard = Controller()
    
    print("🚀 Starting Simulation in 3 seconds...")
    print("👉 SWITCH TO A TEXT EDITOR NOW (Notepad/VS Code blank file)!")
    time.sleep(3)
    
    # Text to type with intentional typos
    text_to_type = "hello wrold how r u today science is incredible"
    
    print(f"⌨  Simulating: '{text_to_type}'")
    
    for char in text_to_type:
        keyboard.type(char)
        time.sleep(0.1) # Simulate human typing speed
        
    print("\n✅ Simulation Complete.")

if __name__ == "__main__":
    simulate_typing()
