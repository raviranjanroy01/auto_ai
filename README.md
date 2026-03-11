# Desktop G-Board — Windows Omni-Input AI Assistant

A Windows-based background service providing **global text prediction**, **autocorrect**, and **AI code assistance** (like GitHub Copilot, but for every app).

## Features

- **Global Keyboard Hook** — Captures keystrokes system-wide via C++ `WH_KEYBOARD_LL` with <5ms latency
- **Auto-Correct** — Context-aware spelling correction (edit distance + n-gram + dictionary)
- **Next-Word Prediction** — N-gram + optional local LLM (1B parameter model via llama.cpp)
- **AI Code Assist** — Hotkey-triggered code completion via Claude / GPT-4 (Ctrl+J)
- **Elaborate** — Expand/rewrite text with AI (Ctrl+E)
- **Caret Tracking** — Overlay follows the text cursor using GetGUIThreadInfo + UI Automation
- **Process Detection** — Auto-switches to "code mode" in VS Code, Visual Studio, PyCharm, etc.
- **Per-Window Context** — 2048-char sliding window buffer per application
- **System Tray** — Runs as a background service with tray icon, start-on-boot support
- **User Learning** — Personalized predictions that improve over time

## Architecture

```
Keystroke → C++ Hook → Named Pipe → Python Orchestrator → Inference Engine → UI Overlay
                                          │                     │
                                    Context Manager       ┌─────┴─────┐
                                    (2048 char/window)    LOCAL    CLOUD
                                                         n-gram   Claude
                                                         LLM 1B   GPT-4
```

See [docs/architecture.md](docs/architecture.md) for the full system design diagram.

## Project Structure

```
desktop-gboard/
├── main.py                     # Entry point 
├── config/                     # Configuration (YAML + defaults)
│   ├── settings.py
│   └── default.yaml
├── core/                       # Core system services
│   ├── hook/                   # C++ keyboard hook (WH_KEYBOARD_LL)
│   │   ├── keyboard_hook.cpp   # Hook implementation + lock-free queue
│   │   ├── ipc_bridge.cpp      # Named Pipe IPC to Python
│   │   ├── hook_service.cpp    # Standalone service executable
│   │   └── CMakeLists.txt      # Build system
│   ├── hook_bridge.py          # Python-side IPC reader + pynput fallback
│   ├── orchestrator.py         # Central coordination loop
│   ├── context_manager.py      # Sliding window buffer (2048 chars)
│   ├── caret_tracker.py        # Multi-strategy caret position tracking
│   └── process_detector.py     # Active process monitoring
├── inference/                  # Hybrid AI inference engine
│   ├── engine.py               # Coordinator (local + cloud)
│   ├── decision_logic.py       # Route: local vs cloud
│   ├── local_engine.py         # N-gram / llama.cpp / ONNX
│   └── cloud_engine.py         # Claude / GPT-4 API
├── ui/                         # User interface
│   ├── overlay.py              # Transparent prediction popup (PySide6)
│   └── system_tray.py          # System tray app + start-on-boot
├── src/                        # Core AI modules (autocorrect, prediction, user model)
├── scripts/                    # Build & setup scripts
├── data/                       # Dictionaries & trained models
└── tests/                      # Test suite
```

## Setup

### Prerequisites
- Python 3.9+
- Windows 10/11
- (Optional) CMake + MSVC for building the C++ hook service

### Installation

```bash
# Clone the repository
git clone https://github.com/raviranjanroy01/auto_ai.git
cd auto_ai

# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up the dictionary (downloads NLTK corpus + builds n-gram model)
python scripts/setup_dictionary.py
```

### Quick Start

```bash
# Launch Desktop G-Board (uses pynput fallback hook)
python main.py

# Or use the batch file
start_gboard.bat

# Console mode (no system tray)
python main.py --console

# Offline mode (no cloud API calls)
python main.py --offline
```

### Building the C++ Hook Service (Optional — Better Performance)

```bash
# Requires CMake + Visual Studio Build Tools
python scripts/build_hook.py

# Then launch with native hook mode
python main.py --hook native
```

### Cloud API Setup (Optional)

Set environment variables for AI code assist:
```bash
set ANTHROPIC_API_KEY=sk-ant-...
set OPENAI_API_KEY=sk-...
```

Or configure in `config.yaml`.

### Hotkeys

| Hotkey | Action |
|--------|--------|
| Ctrl+J | Code Assist (sends context to Claude/GPT-4) |
| Ctrl+E | Elaborate (expand/rewrite selected text) |
| Esc | Dismiss overlay |

### Running Tests

```bash
python -m pytest tests/ -v
```

## Roadmap

- **Phase 1 (Current):** Global hook + autocorrect + n-gram prediction + overlay
- **Phase 2:** Local LLM integration (TinyLlama 1B via llama.cpp)
- **Phase 3:** Full Cloud API integration (Claude + GPT-4 code assist)
- **Phase 4:** Multi-language support, sentence completion, voice integration

## License

MIT License — see [LICENSE](LICENSE) for details.
