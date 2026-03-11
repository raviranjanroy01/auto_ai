"""
Desktop G-Board — Hybrid Inference Decision Logic
===================================================
Routes inference requests between:
  - LOCAL PATH:  ≤100ms latency — next-word/phrase prediction
                  (tiny 1B model via llama.cpp / ONNX Runtime)
  - CLOUD PATH:  Triggered by hotkeys — "Code Assist" / "Elaborate"
                  (Claude / GPT-4 via API)

Decision factors:
  1. Request type (prediction vs code-assist vs elaborate)
  2. Latency budget
  3. Context mode (code vs general vs browser)
  4. Network availability
  5. User preference (offline-only mode)
"""

import time
import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, List

logger = logging.getLogger(__name__)


class RequestType(Enum):
    """Types of inference requests."""
    NEXT_WORD = auto()          # Fast prediction — always local
    NEXT_PHRASE = auto()        # Multi-word prediction — local
    AUTOCORRECT = auto()        # Spelling correction — local (n-gram + dictionary)
    CODE_ASSIST = auto()        # Code completion — cloud (hotkey triggered)
    ELABORATE = auto()          # Expand/rewrite text — cloud (hotkey triggered)
    SUMMARIZE = auto()          # Summarize context — cloud
    TRANSLATE = auto()          # Translate text — cloud


class InferencePath(Enum):
    """Which engine handles the request."""
    LOCAL = "local"
    CLOUD = "cloud"
    LOCAL_THEN_CLOUD = "local_then_cloud"   # Try local first, fallback to cloud
    SKIP = "skip"                           # Don't run inference (e.g., modifier keys)


@dataclass
class InferenceRequest:
    """A request to the inference engine."""
    request_type: RequestType
    context: str                    # The text context (up to 2048 chars)
    current_word: str = ""          # Word being typed (for autocomplete)
    context_mode: str = "general"   # "code", "browser", "office", "general"
    process_name: str = ""          # Active process (for code-assist context)
    max_latency_ms: float = 100.0   # Latency budget
    top_k: int = 5                  # Number of predictions to return
    timestamp: float = field(default_factory=time.time)
    hotkey: Optional[str] = None    # Which hotkey triggered this (if any)


@dataclass
class InferenceResult:
    """Result from the inference engine."""
    predictions: List[tuple]    # [(word, probability), ...]
    source: InferencePath       # Which engine produced this
    latency_ms: float           # How long inference took
    model_name: str = ""        # Which model was used
    raw_text: str = ""          # Raw generated text (for code-assist/elaborate)
    error: Optional[str] = None


class DecisionLogic:
    """
    Routes inference requests to the appropriate engine.

    Rules:
      1. NEXT_WORD / NEXT_PHRASE / AUTOCORRECT → LOCAL (100ms budget)
      2. CODE_ASSIST → CLOUD (Claude/GPT-4, context_mode must be "code")
      3. ELABORATE / SUMMARIZE / TRANSLATE → CLOUD
      4. If cloud is unavailable, degrade gracefully to local
      5. If offline_only=True, everything goes local
    """

    def __init__(self, offline_only: bool = False, cloud_available: bool = True):
        self.offline_only = offline_only
        self.cloud_available = cloud_available
        self._cloud_failure_count = 0
        self._max_cloud_failures = 3  # Circuit breaker

    def decide(self, request: InferenceRequest) -> InferencePath:
        """Determine which inference path to use for a request."""

        # Fast-path: prediction and correction always go local
        if request.request_type in (
            RequestType.NEXT_WORD,
            RequestType.NEXT_PHRASE,
            RequestType.AUTOCORRECT,
        ):
            return InferencePath.LOCAL

        # Cloud requests
        if request.request_type in (
            RequestType.CODE_ASSIST,
            RequestType.ELABORATE,
            RequestType.SUMMARIZE,
            RequestType.TRANSLATE,
        ):
            # Check if we can use cloud
            if self.offline_only:
                logger.info("Offline mode — routing %s to LOCAL", request.request_type.name)
                return InferencePath.LOCAL

            if not self.cloud_available or self._cloud_failure_count >= self._max_cloud_failures:
                logger.warning("Cloud unavailable (failures=%d) — falling back to LOCAL",
                             self._cloud_failure_count)
                return InferencePath.LOCAL

            # Code assist only makes sense in code mode
            if request.request_type == RequestType.CODE_ASSIST and request.context_mode != "code":
                logger.info("CODE_ASSIST in non-code context — using LOCAL_THEN_CLOUD")
                return InferencePath.LOCAL_THEN_CLOUD

            return InferencePath.CLOUD

        return InferencePath.LOCAL

    def report_cloud_success(self):
        """Reset the circuit breaker on successful cloud call."""
        self._cloud_failure_count = 0

    def report_cloud_failure(self):
        """Increment the circuit breaker on cloud failure."""
        self._cloud_failure_count += 1
        if self._cloud_failure_count >= self._max_cloud_failures:
            logger.error("Cloud circuit breaker OPEN — too many failures. "
                        "All requests will be routed locally.")

    def get_system_prompt(self, context_mode: str) -> str:
        """Get the appropriate system prompt for cloud API calls."""
        prompts = {
            "code": (
                "You are an expert programming assistant embedded in a desktop typing tool. "
                "The user is writing code. Provide concise, correct code completions. "
                "Match the language and style of the surrounding code. "
                "Do NOT include explanations unless asked. Return only the code continuation."
            ),
            "browser": (
                "You are a helpful writing assistant. The user is typing in a web browser. "
                "Provide natural, contextually appropriate text continuations. "
                "Be concise."
            ),
            "office": (
                "You are a professional writing assistant. The user is writing a document. "
                "Provide polished, professional text continuations that match the document's "
                "tone and style."
            ),
            "general": (
                "You are a helpful typing assistant. Provide concise, natural text "
                "continuations based on the context."
            ),
        }
        return prompts.get(context_mode, prompts["general"])
