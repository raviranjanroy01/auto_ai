"""
Desktop G-Board — Local Inference Engine
==========================================
Handles fast (<100ms) local inference for:
  - Next-word prediction (n-gram model)
  - Autocorrection (edit distance + dictionary + context)
  - Phrase completion (tiny LLM via llama.cpp or ONNX Runtime)

Architecture:
  - N-gram model: Always available, <5ms inference
  - Tiny LLM (optional): 1B parameter quantized model via llama.cpp
  - ONNX model (optional): Optimized transformer via ONNX Runtime

The n-gram model is the foundation; LLM/ONNX are optional upgrades
that can be swapped in without changing the interface.
"""

import time
import os
import logging
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)


class LocalEngine:
    """
    Local inference engine for fast prediction and correction.

    Wraps the existing n-gram model, autocorrector, and optionally
    a tiny LLM for higher-quality completions.
    """

    def __init__(self, config: dict = None):
        self._config = config or {}
        self._ngram_model = None
        self._autocorrector = None
        self._dictionary = None
        self._llm_model = None
        self._onnx_session = None
        self._is_ready = False

    def initialize(self,
                   dictionary=None,
                   ngram_model=None,
                   autocorrector=None):
        """
        Initialize the local engine with the existing AI components.

        Args:
            dictionary: Dictionary instance from core.autocorrect
            ngram_model: NGramModel instance from core.prediction
            autocorrector: AutoCorrector instance from core.autocorrect
        """
        self._dictionary = dictionary
        self._ngram_model = ngram_model
        self._autocorrector = autocorrector
        self._is_ready = True

        # Try to load optional LLM backend
        self._try_load_llm()
        self._try_load_onnx()

        logger.info("Local engine initialized. LLM=%s, ONNX=%s",
                   "yes" if self._llm_model else "no",
                   "yes" if self._onnx_session else "no")

    def predict_next_word(self, context: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """
        Predict the next word(s) given context.
        Target latency: <10ms (n-gram), <100ms (LLM).
        """
        start = time.perf_counter()
        predictions = []

        # 1. Try LLM first if available (higher quality)
        if self._llm_model:
            try:
                predictions = self._llm_predict(context, top_k)
                if predictions:
                    latency = (time.perf_counter() - start) * 1000
                    logger.debug("LLM prediction in %.1fms: %s", latency,
                               [w for w, _ in predictions])
                    return predictions
            except Exception as e:
                logger.warning("LLM prediction failed: %s", e)

        # 2. Try ONNX model
        if self._onnx_session and not predictions:
            try:
                predictions = self._onnx_predict(context, top_k)
                if predictions:
                    latency = (time.perf_counter() - start) * 1000
                    logger.debug("ONNX prediction in %.1fms", latency)
                    return predictions
            except Exception as e:
                logger.warning("ONNX prediction failed: %s", e)

        # 3. Fallback to n-gram model (always available)
        if self._ngram_model:
            predictions = self._ngram_model.predict(context, top_k=top_k)
            latency = (time.perf_counter() - start) * 1000
            logger.debug("N-gram prediction in %.1fms: %s", latency,
                       [w for w, _ in predictions])

        return predictions

    def complete_word(self, prefix: str, context: str = "", sentence: str = "", top_k: int = 5) -> List[Tuple[str, float]]:
        """
        Complete a partially typed word using sentence + n-gram context.
        Like G-Board: "I am go" -> "going", "good" (context-aware).
        Target latency: <10ms.

        Combines (in priority order):
          1. N-gram context-aware prefix predictions (uses sentence context)
          2. Dictionary prefix search (frequency-ranked)
          3. N-gram vocabulary scan (fallback)

        Args:
            prefix: The partial word being typed (e.g., "go").
            context: The n-gram context (last few completed words).
            sentence: The full sentence typed so far (richer context).
            top_k: Number of completions to return.
        """
        if not prefix or len(prefix) < 2:
            return []

        start = time.perf_counter()
        prefix_lower = prefix.lower()
        seen = set()
        completions = []

        # Use whichever context is richer
        effective_context = sentence.strip() if sentence.strip() else context

        # 1. N-gram predictions filtered by prefix (context-aware, highest quality)
        #    Uses predict_with_prefix for efficient context+prefix matching
        if self._ngram_model and effective_context:
            if hasattr(self._ngram_model, 'predict_with_prefix'):
                ngram_preds = self._ngram_model.predict_with_prefix(
                    effective_context, prefix_lower, top_k=15
                )
            else:
                ngram_preds = self._ngram_model.predict(effective_context, top_k=30)
                ngram_preds = [
                    (w, p) for w, p in ngram_preds
                    if w.startswith(prefix_lower) and w != prefix_lower
                ]

            for word, prob in ngram_preds:
                if word not in seen:
                    # Boost: context-aware matches score 3x to dominate
                    completions.append((word, prob * 3.0))
                    seen.add(word)

        # 2. Dictionary prefix search (frequency-ranked)
        if self._dictionary:
            dict_matches = self._dictionary.search_prefix(prefix_lower, top_k=20)
            max_freq = max((f for _, f in dict_matches), default=1)
            for word, freq in dict_matches:
                if word not in seen:
                    completions.append((word, freq / max_freq))  # Normalize to 0-1
                    seen.add(word)

        # 3. N-gram vocabulary scan (low-priority fallback)
        if self._ngram_model and hasattr(self._ngram_model, 'vocabulary'):
            for word in self._ngram_model.vocabulary:
                if word.startswith(prefix_lower) and word != prefix_lower and word not in seen:
                    completions.append((word, 0.1))
                    seen.add(word)
                    if len(completions) >= top_k * 3:
                        break

        # Sort by score descending and return top_k
        completions.sort(key=lambda x: x[1], reverse=True)
        latency = (time.perf_counter() - start) * 1000
        logger.debug("Word completion for '%s' (ctx='%s') in %.1fms: %s",
                   prefix, effective_context[:40], latency,
                   [w for w, _ in completions[:top_k]])

        return completions[:top_k]

    def autocorrect(self, word: str, context: str = "") -> str:
        """
        Check and correct a word. Target latency: <50ms.
        """
        if not self._autocorrector:
            return word

        start = time.perf_counter()
        corrected = self._autocorrector.correct(word, context=context)
        latency = (time.perf_counter() - start) * 1000

        if corrected != word:
            logger.debug("Autocorrect: '%s' -> '%s' in %.1fms", word, corrected, latency)

        return corrected

    def complete_phrase(self, context: str, max_tokens: int = 10) -> str:
        """
        Generate a multi-word completion. Uses LLM if available,
        otherwise chains n-gram predictions.
        """
        if self._llm_model:
            try:
                return self._llm_complete(context, max_tokens)
            except Exception as e:
                logger.warning("LLM completion failed: %s", e)

        # Fallback: chain n-gram predictions
        if self._ngram_model:
            words = []
            current_ctx = context
            for _ in range(max_tokens):
                preds = self._ngram_model.predict(current_ctx, top_k=1)
                if not preds:
                    break
                word = preds[0][0]
                words.append(word)
                current_ctx += " " + word
            return " ".join(words)

        return ""

    @property
    def is_ready(self) -> bool:
        return self._is_ready

    # ─── LLM Backend (llama.cpp) ─────────────────────────────────

    def _try_load_llm(self):
        """Try to load a quantized model via llama-cpp-python."""
        model_path = self._config.get("llm_model_path", "")
        if not model_path or not os.path.exists(model_path):
            model_path = os.path.join("data", "models", "tinyllama-1b.Q4_K_M.gguf")
            if not os.path.exists(model_path):
                logger.info("No local LLM model found at %s. Using n-gram only.", model_path)
                return

        try:
            from llama_cpp import Llama
            self._llm_model = Llama(
                model_path=model_path,
                n_ctx=512,          # Small context for speed
                n_threads=4,
                n_gpu_layers=0,     # CPU-only for now
                verbose=False,
            )
            logger.info("Loaded local LLM: %s", model_path)
        except ImportError:
            logger.info("llama-cpp-python not installed. LLM backend unavailable.")
        except Exception as e:
            logger.warning("Failed to load LLM model: %s", e)

    def _llm_predict(self, context: str, top_k: int) -> List[Tuple[str, float]]:
        """Get next-word predictions from the LLM."""
        if not self._llm_model:
            return []

        output = self._llm_model(
            context,
            max_tokens=1,
            top_k=top_k,
            temperature=0.3,
            echo=False,
        )

        if output and "choices" in output:
            text = output["choices"][0].get("text", "").strip()
            if text:
                return [(text.split()[0], 0.9)]
        return []

    def _llm_complete(self, context: str, max_tokens: int) -> str:
        """Generate a multi-token completion from the LLM."""
        if not self._llm_model:
            return ""

        output = self._llm_model(
            context,
            max_tokens=max_tokens,
            temperature=0.5,
            echo=False,
        )

        if output and "choices" in output:
            return output["choices"][0].get("text", "").strip()
        return ""

    # ─── ONNX Backend ───────────────────────────────────────────

    def _try_load_onnx(self):
        """Try to load an ONNX model for fast inference."""
        model_path = self._config.get("onnx_model_path", "")
        if not model_path:
            model_path = os.path.join("data", "models", "predictor.onnx")
        if not os.path.exists(model_path):
            return

        try:
            import onnxruntime as ort
            self._onnx_session = ort.InferenceSession(
                model_path,
                providers=["CPUExecutionProvider"]
            )
            logger.info("Loaded ONNX model: %s", model_path)
        except ImportError:
            logger.info("onnxruntime not installed. ONNX backend unavailable.")
        except Exception as e:
            logger.warning("Failed to load ONNX model: %s", e)

    def _onnx_predict(self, context: str, top_k: int) -> List[Tuple[str, float]]:
        """Run prediction through the ONNX model."""
        # Placeholder — actual implementation depends on model architecture
        # Typically: tokenize context -> run inference -> decode top-k tokens
        return []
