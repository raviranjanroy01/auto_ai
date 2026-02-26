# 🚀 AutoAI — Intelligent Typing Assistant

An AI-powered typing assistant that provides **auto-correction** and **next-word prediction**, personalized to each user's writing style.

## ✨ Features

- **Auto-Correct** — Context-aware spelling correction using edit distance + language models
- **Next-Word Prediction** — N-gram based prediction that learns from your typing patterns
- **User Personalization** — Adapts to your vocabulary, writing style, and common phrases
- **Cross-Platform** — Designed for both desktop and mobile (Phase 3)

## 📁 Project Structure

```
auto_ai/
├── src/                        # Core source code
│   ├── autocorrect/            # Auto-correction engine
│   │   ├── __init__.py
│   │   ├── corrector.py        # Main correction logic
│   │   ├── edit_distance.py    # Levenshtein distance algorithms
│   │   └── dictionary.py       # Dictionary/vocabulary management
│   ├── prediction/             # Next-word prediction engine
│   │   ├── __init__.py
│   │   ├── predictor.py        # Main prediction logic
│   │   └── ngram.py            # N-gram model implementation
│   ├── user_model/             # User personalization
│   │   ├── __init__.py
│   │   ├── profile.py          # User profile management
│   │   └── learner.py          # Learning from user input
│   ├── utils/                  # Shared utilities
│   │   ├── __init__.py
│   │   ├── text_processing.py  # Text cleaning & tokenization
│   │   └── config.py           # Configuration management
│   └── __init__.py
├── data/                       # Data files
│   ├── dictionaries/           # Word dictionaries
│   └── models/                 # Trained model files
├── tests/                      # Unit & integration tests
│   ├── test_autocorrect.py
│   ├── test_prediction.py
│   └── test_user_model.py
├── app/                        # Application layer (UI/API)
│   └── desktop/                # Desktop app prototype
│       └── __init__.py
├── docs/                       # Documentation
│   └── architecture.md         # System architecture overview
├── todos/                      # Project planning
│   └── Roadmap                 # Development roadmap
├── .gitignore                  # Git ignore rules
├── requirements.txt            # Python dependencies
├── setup.py                    # Package setup
└── README.md                   # This file
```

## 🛠️ Setup

### Prerequisites
- Python 3.9+
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/raviranjanroy01/auto_ai.git
cd auto_ai

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Running Tests

```bash
python -m pytest tests/
```

## 🗺️ Roadmap

- **Phase 1:** Core Engine (MVP) — Auto-correct, next-word prediction, desktop prototype
- **Phase 2:** Smarter Models — Transformer upgrade, context-aware corrections
- **Phase 3:** Cross-Platform — Mobile keyboard, shared engine core
- **Phase 4:** Advanced Features — Multi-language, sentence completion, voice integration

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
