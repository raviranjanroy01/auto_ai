# Desktop G-Board — System Architecture

## Overview

Desktop G-Board is a Windows-based background service providing global text prediction,
autocorrect, and AI code assistance. It uses a hybrid architecture:

- **C++ Hook Layer**: Low-level `WH_KEYBOARD_LL` hook for sub-5ms key capture
- **Python Orchestrator**: AI/ML logic, context management, inference routing
- **Hybrid Inference**: Local n-gram/LLM models + Cloud API (Claude/GPT-4) fallback
- **Transparent Overlay**: Hardware-accelerated UI following the text cursor

## System Design Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         KEYSTROKE PIPELINE                              │
│                                                                         │
│  ┌──────────┐   Named    ┌──────────────┐        ┌──────────────────┐  │
│  │ C++ Hook │───Pipe────→│   Python     │───────→│  Inference       │  │
│  │ Service  │  (IPC)     │ Orchestrator │        │  Engine          │  │
│  │          │            │              │        │                  │  │
│  │ WH_KEY   │            │ • Key Router │        │ ┌──────────────┐ │  │
│  │ BOARD_LL │            │ • Hotkey Mgr │   ┌───→│ │ LOCAL PATH   │ │  │
│  │          │            │ • Word Proc  │   │    │ │ • N-gram     │ │  │
│  │ Lock-free│            │              │   │    │ │ • LLM (1B)   │ │  │
│  │ Queue    │            └──────┬───────┘   │    │ │ • ONNX       │ │  │
│  └──────────┘                   │           │    │ │ (<100ms)     │ │  │
│       ▲                         │    Decision│    │ └──────────────┘ │  │
│       │                         │    Logic───┘    │ ┌──────────────┐ │  │
│  ┌────┴─────┐            ┌──────▼───────┐   │    │ │ CLOUD PATH   │ │  │
│  │ Keyboard │            │   Context    │   └───→│ │ • Claude     │ │  │
│  │ (User)   │            │   Manager   │        │ │ • GPT-4      │ │  │
│  └──────────┘            │ (2048 char  │        │ │ (Hotkey)     │ │  │
│                          │  per window)│        │ └──────────────┘ │  │
│                          └──────┬───────┘        └────────┬─────────┘  │
│                                 │                         │            │
│                    ┌────────────┼────────────┐            │            │
│                    │            │            │            │            │
│             ┌──────▼──┐  ┌─────▼─────┐ ┌────▼───┐       │            │
│             │ Process │  │   Caret   │ │  User  │       │            │
│             │Detector │  │  Tracker  │ │ Model  │       │            │
│             │         │  │           │ │        │       │            │
│             │Code.exe │  │ GUI Info  │ │Learner │       │            │
│             │→"code"  │  │ + UIA     │ │Profile │       │            │
│             └─────────┘  └─────┬─────┘ └────────┘       │            │
│                                │                         │            │
│                         ┌──────▼─────────────────────────▼──────┐     │
│                         │           UI OVERLAY                   │     │
│                         │  • Transparent popup near caret        │     │
│                         │  • Prediction list (1-5)               │     │
│                         │  • Code completion panel               │     │
│                         │  • System tray icon + menu             │     │
│                         └────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────┘
```

## File Structure

```
desktop-gboard/
├── main.py                          # Entry point (tray + overlay + orchestrator)
├── config/
│   ├── settings.py                  # Config manager (YAML + defaults)
│   └── default.yaml                 # Default configuration template
├── core/
│   ├── hook/                        # C++ low-level keyboard hook
│   │   ├── CMakeLists.txt           # Build system
│   │   ├── keyboard_hook.h          # Header: KeyEvent struct, queue, API
│   │   ├── keyboard_hook.cpp        # WH_KEYBOARD_LL implementation
│   │   ├── ipc_bridge.cpp           # Named Pipe writer thread
│   │   └── hook_service.cpp         # Standalone service executable
│   ├── hook_bridge.py               # Python-side IPC reader + pynput fallback
│   ├── orchestrator.py              # Central coordination loop
│   ├── context_manager.py           # Sliding window buffer (2048 chars/window)
│   ├── caret_tracker.py             # GetGUIThreadInfo + UI Automation
│   └── process_detector.py          # Active process monitoring & mode detection
├── inference/
│   ├── engine.py                    # Hybrid inference coordinator
│   ├── decision_logic.py            # Route requests: local vs cloud
│   ├── local_engine.py              # N-gram + llama.cpp + ONNX
│   └── cloud_engine.py              # Claude / GPT-4 API calls
├── ui/
│   ├── overlay.py                   # Transparent prediction popup (PySide6/tkinter)
│   └── system_tray.py               # System tray icon + menu + boot config
├── src/                             # Core AI engines (from v0.1)
│   ├── autocorrect/                 # Edit distance + dictionary + corrector
│   ├── prediction/                  # N-gram language model + predictor
│   ├── user_model/                  # User profile + learning engine
│   └── utils/                       # Text processing + config utilities
├── scripts/
│   ├── build_hook.py                # Build C++ hook service via CMake
│   ├── setup_dictionary.py          # Download NLTK corpus + build dictionary
│   └── simulate_test.py             # Simulate typing for integration testing
├── data/
│   ├── dictionaries/english.txt     # Word dictionary with frequencies
│   └── models/                      # Trained models (n-gram, LLM, ONNX)
├── tests/                           # Test suite
├── docs/                            # Architecture docs
├── requirements.txt                 # Python dependencies
├── setup.py                         # Package installer
└── start_gboard.bat                 # Quick-start launcher
```

## Data Flow

1. **User types** → C++ hook captures keystroke in <0.5ms
2. **Lock-free queue** → Event enqueued without blocking the hook
3. **Named Pipe** → IPC Writer sends to Python in <1ms
4. **Orchestrator** → Routes to Context Manager, checks hotkeys
5. **Context Manager** → Updates per-window sliding buffer (2048 chars)
6. **Decision Logic** → Routes to LOCAL or CLOUD path
7. **Local Path** → N-gram model predicts in <10ms (or LLM in <100ms)
8. **Cloud Path** → Claude/GPT-4 called for Code Assist (hotkey only)
9. **UI Overlay** → Predictions displayed near caret position
10. **User accepts** → Text injected via simulated keystrokes

## Key Design Decisions

- **Dual-process architecture** — C++ hook runs at HIGH priority for responsiveness;
  Python AI engine runs in a separate process at normal priority
- **Lock-free SPSC queue** — Zero-allocation hot path in the hook callback
- **Named Pipe IPC** — Simple, low-latency, cross-language communication
- **Hybrid inference** — Fast local predictions + powerful cloud completions
- **Circuit breaker** — Auto-disables cloud after repeated failures
- **Per-window context** — Each app gets its own 2048-char sliding window
- **Process detection** — Auto-switches to "code mode" in VS Code/IDEs
- **Multi-strategy caret tracking** — GetGUIThreadInfo → UIA → GetCaretPos
- **Graceful degradation** — Every component has a fallback (native→pynput, PySide6→tkinter, cloud→local)
