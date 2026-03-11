"""
Desktop G-Board — Hybrid Inference Engine
==========================================
The main inference engine that coordinates local and cloud inference
based on the Decision Logic module.

Flow:
  Keystroke → Context Manager → InferenceRequest → DecisionLogic
      ↓ LOCAL path                    ↓ CLOUD path
    N-gram / LLM                  Claude / GPT-4
      ↓                              ↓
    InferenceResult              InferenceResult
      ↓                              ↓
    UI Overlay ←──────────────────────┘
"""

import time
import logging
import threading
from typing import List, Tuple, Optional, Callable

from .decision_logic import (
    DecisionLogic, InferenceRequest, InferenceResult,
    InferencePath, RequestType
)
from .local_engine import LocalEngine
from .cloud_engine import CloudEngine

logger = logging.getLogger(__name__)


class HybridInferenceEngine:
    """
    Coordinates local and cloud inference.
    Thread-safe — can be called from the orchestrator thread.
    """

    def __init__(self, config: dict = None):
        self._config = config or {}

        # Decision logic
        self._decision = DecisionLogic(
            offline_only=self._config.get("offline_only", False),
            cloud_available=True,
        )

        # Engines
        self.local = LocalEngine(config=self._config.get("local", {}))
        self.cloud = CloudEngine(config=self._config.get("cloud", {}))

        # Update cloud availability
        self._decision.cloud_available = self.cloud.is_available

        # Lock for thread safety
        self._lock = threading.Lock()

        # Stats
        self.total_requests = 0
        self.local_requests = 0
        self.cloud_requests = 0

    def initialize(self, dictionary=None, ngram_model=None, autocorrector=None):
        """Initialize the local engine with AI components."""
        self.local.initialize(
            dictionary=dictionary,
            ngram_model=ngram_model,
            autocorrector=autocorrector,
        )

    def infer(self, request: InferenceRequest) -> InferenceResult:
        """
        Run inference on a request, routing to the appropriate engine.

        Returns:
            InferenceResult with predictions and metadata.
        """
        start = time.perf_counter()
        self.total_requests += 1

        # Decide which path
        path = self._decision.decide(request)

        if path == InferencePath.SKIP:
            return InferenceResult(
                predictions=[],
                source=InferencePath.SKIP,
                latency_ms=0,
            )

        if path == InferencePath.LOCAL:
            return self._run_local(request, start)

        if path == InferencePath.CLOUD:
            return self._run_cloud(request, start)

        if path == InferencePath.LOCAL_THEN_CLOUD:
            # Get local results immediately, then try cloud
            local_result = self._run_local(request, start)
            # Fire cloud request in background
            self._run_cloud_async(request, callback=None)
            return local_result

        return InferenceResult(
            predictions=[],
            source=InferencePath.SKIP,
            latency_ms=0,
            error="Unknown inference path",
        )

    def infer_async(self, request: InferenceRequest,
                    callback: Callable[[InferenceResult], None]):
        """
        Run inference asynchronously. Result delivered via callback.
        Useful for cloud requests that shouldn't block the UI.
        """
        thread = threading.Thread(
            target=self._async_infer,
            args=(request, callback),
            daemon=True,
            name="AsyncInfer",
        )
        thread.start()

    # ─── Internal ────────────────────────────────────────────────

    def _run_local(self, request: InferenceRequest, start: float) -> InferenceResult:
        """Execute local inference."""
        self.local_requests += 1

        predictions = []
        raw_text = ""

        if request.request_type == RequestType.AUTOCORRECT:
            corrected = self.local.autocorrect(request.current_word, request.context)
            if corrected != request.current_word:
                predictions = [(corrected, 1.0)]
            raw_text = corrected

        elif request.request_type in (RequestType.NEXT_WORD, RequestType.NEXT_PHRASE):
            predictions = self.local.predict_next_word(request.context, request.top_k)
            if request.request_type == RequestType.NEXT_PHRASE and not predictions:
                phrase = self.local.complete_phrase(request.context)
                if phrase:
                    raw_text = phrase

        else:
            # For cloud-type requests going local (fallback), do phrase completion
            raw_text = self.local.complete_phrase(request.context, max_tokens=20)
            if raw_text:
                predictions = [(raw_text.split()[0], 0.5)] if raw_text.split() else []

        latency = (time.perf_counter() - start) * 1000
        return InferenceResult(
            predictions=predictions,
            source=InferencePath.LOCAL,
            latency_ms=latency,
            model_name="ngram" if not self.local._llm_model else "local-llm",
            raw_text=raw_text,
        )

    def _run_cloud(self, request: InferenceRequest, start: float) -> InferenceResult:
        """Execute cloud inference."""
        self.cloud_requests += 1
        system_prompt = self._decision.get_system_prompt(request.context_mode)

        try:
            if request.request_type == RequestType.CODE_ASSIST:
                result_text = self.cloud.code_assist(request.context)
            elif request.request_type == RequestType.ELABORATE:
                result_text = self.cloud.elaborate(request.context)
            else:
                result_text = self.cloud.complete(
                    context=request.context,
                    system_prompt=system_prompt,
                    max_tokens=150,
                )

            self._decision.report_cloud_success()

            latency = (time.perf_counter() - start) * 1000
            predictions = []
            if result_text:
                # First word as a prediction
                first_word = result_text.split()[0] if result_text.split() else ""
                if first_word:
                    predictions = [(first_word, 0.95)]

            return InferenceResult(
                predictions=predictions,
                source=InferencePath.CLOUD,
                latency_ms=latency,
                model_name="claude" if "anthropic" in str(type(self.cloud)) else "gpt-4",
                raw_text=result_text,
            )

        except Exception as e:
            self._decision.report_cloud_failure()
            latency = (time.perf_counter() - start) * 1000
            logger.error("Cloud inference failed: %s", e)

            return InferenceResult(
                predictions=[],
                source=InferencePath.CLOUD,
                latency_ms=latency,
                error=str(e),
            )

    def _run_cloud_async(self, request: InferenceRequest,
                         callback: Optional[Callable]):
        """Run cloud inference in a background thread."""
        def _bg():
            start = time.perf_counter()
            result = self._run_cloud(request, start)
            if callback:
                callback(result)

        thread = threading.Thread(target=_bg, daemon=True, name="CloudInfer")
        thread.start()

    def _async_infer(self, request: InferenceRequest,
                     callback: Callable[[InferenceResult], None]):
        """Background thread wrapper for async inference."""
        start = time.perf_counter()
        result = self.infer(request)
        callback(result)
