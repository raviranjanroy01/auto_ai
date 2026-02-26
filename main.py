"""
AutoAI — Desktop Launcher
=========================
Run this to launch the full floating assistant.
"""

import sys
import os

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from app.desktop.ui import AutoAIFloatingUI

if __name__ == "__main__":
    print("✨ Launching AutoAI Desktop Assistant...")
    print("💡 Tip: You can drag the window by its top handle.")
    print("💡 Tip: Open Notepad or VS Code and type to see it in action.")
    
    app = AutoAIFloatingUI()
    try:
        app.mainloop()
    except KeyboardInterrupt:
        app.quit_app()
