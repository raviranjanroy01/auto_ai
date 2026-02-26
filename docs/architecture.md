# AutoAI — System Architecture

## Overview

AutoAI is a modular typing assistant built with a layered architecture:

```
┌──────────────────────────────────────────────┐
│              Application Layer               │
│          (Desktop UI / Mobile IME)           │
├──────────────────────────────────────────────┤
│              Engine Layer                    │
│  ┌─────────────┐  ┌──────────────────────┐  │
│  │ AutoCorrect │  │  Word Prediction     │  │
│  │  - Edit Dist│  │  - N-Gram Model      │  │
│  │  - Dictionary│  │  - Backoff Strategy  │  │
│  └─────────────┘  └──────────────────────┘  │
├──────────────────────────────────────────────┤
│            Personalization Layer             │
│  ┌──────────────┐  ┌────────────────────┐   │
│  │ User Profile │  │  User Learner      │   │
│  │  - Vocab     │  │  - Pattern Mining  │   │
│  │  - Patterns  │  │  - Personal Model  │   │
│  └──────────────┘  └────────────────────┘   │
├──────────────────────────────────────────────┤
│              Utilities Layer                 │
│     Text Processing  |  Configuration       │
└──────────────────────────────────────────────┘
```

## Data Flow

1. **User types text** → Application layer captures input
2. **Auto-correct** checks each word against the dictionary
3. If misspelled, **edit distance** finds candidates, ranked by frequency
4. **N-gram model** predicts next word based on context
5. **User learner** records patterns to improve future suggestions
6. **User profile** persists personalization data across sessions

## Key Design Decisions

- **Modular architecture** — Each component is independent and testable
- **Backoff strategy** — N-gram model falls back from trigram → bigram → unigram
- **Local-first** — All data stays on-device by default (privacy)
- **Pluggable models** — Easy to swap n-gram for transformer in Phase 2
