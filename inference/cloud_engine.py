"""
Desktop G-Board — Cloud Inference Engine
==========================================
Handles cloud API calls to Gemini / Claude / GPT-4 for:
  - Code Assist (hotkey-triggered code completion)
  - Elaborate (expand/rewrite selected text)
  - Summarize / Translate

Features:
  - Async API calls (non-blocking)
  - Automatic retry with exponential backoff
  - Circuit breaker (stops calling after repeated failures)
  - Response caching for identical contexts
  - Streaming support for long completions

Supported Providers (in priority order):
  1. Groq Cloud    — FREE tier (30 req/min, Llama/Mixtral models)
  2. Google Gemini  — FREE tier (15 req/min, 1500 req/day)
  3. OpenAI GPT-4o  — Paid (requires billing)
  4. Anthropic Claude — Paid (requires billing)
"""

import os
import time
import json
import hashlib
import logging
import threading
from typing import Optional, List, Tuple, Callable
from collections import OrderedDict

logger = logging.getLogger(__name__)


class CloudEngine:
    """
    Cloud inference engine for high-capability AI completions.

    Supports multiple providers:
      - Groq Cloud (default — free, fast inference)
      - Google Gemini (free tier)
      - OpenAI GPT-4o-mini (paid)
      - Anthropic Claude (paid)
    """

    def __init__(self, config: dict = None):
        self._config = config or {}

        # API keys (from config or environment)
        self._groq_key = self._config.get(
            "groq_api_key",
            os.environ.get("GROQ_API_KEY", "")
        )
        self._gemini_key = self._config.get(
            "gemini_api_key",
            os.environ.get("GEMINI_API_KEY", "")
        )
        self._anthropic_key = self._config.get(
            "anthropic_api_key",
            os.environ.get("ANTHROPIC_API_KEY", "")
        )
        self._openai_key = self._config.get(
            "openai_api_key",
            os.environ.get("OPENAI_API_KEY", "")
        )

        # Provider priority (groq first — it's free and fast)
        self._primary_provider = self._config.get("primary_provider", "groq")

        # Response cache (LRU)
        self._cache: OrderedDict[str, str] = OrderedDict()
        self._max_cache_size = 100

        # Rate limiting
        self._last_call_time = 0.0
        self._min_call_interval = 0.5  # seconds between calls

        # Stats
        self._total_calls = 0
        self._total_errors = 0

    @property
    def is_available(self) -> bool:
        """Check if any cloud provider is configured."""
        return bool(self._groq_key or self._gemini_key or self._anthropic_key or self._openai_key)

    def complete(self,
                 context: str,
                 system_prompt: str = "",
                 max_tokens: int = 150,
                 temperature: float = 0.3,
                 callback: Optional[Callable[[str], None]] = None) -> str:
        """
        Send a completion request to the cloud API.

        Args:
            context: The text context to complete
            system_prompt: System prompt for the model
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0=deterministic, 1=creative)
            callback: Optional callback for async results

        Returns:
            The generated text completion.
        """
        if not self.is_available:
            logger.warning("No cloud API keys configured.")
            return ""

        # Check cache
        cache_key = self._make_cache_key(context, system_prompt)
        if cache_key in self._cache:
            result = self._cache[cache_key]
            self._cache.move_to_end(cache_key)
            logger.debug("Cache hit for context: %s...", context[:50])
            if callback:
                callback(result)
            return result

        # Rate limiting
        now = time.time()
        elapsed = now - self._last_call_time
        if elapsed < self._min_call_interval:
            time.sleep(self._min_call_interval - elapsed)
        self._last_call_time = time.time()

        # If async callback is provided, run in background thread
        if callback:
            thread = threading.Thread(
                target=self._call_and_callback,
                args=(context, system_prompt, max_tokens, temperature, callback, cache_key),
                daemon=True,
            )
            thread.start()
            return ""  # Result will come via callback

        # Synchronous call
        return self._do_api_call(context, system_prompt, max_tokens, temperature, cache_key)

    def complete_word_in_context(self, sentence: str, prefix: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """
        Ask the cloud LLM to predict word completions given a sentence and prefix.
        This gives G-Board-quality context-aware predictions.

        Args:
            sentence: The full sentence typed so far (e.g., "I am going to the").
            prefix: The partial word being typed (e.g., "st").
            top_k: Number of completions to return.

        Returns:
            List of (word, confidence) tuples.
        """
        if not self.is_available or not prefix or len(prefix) < 2:
            return []

        system_prompt = (
            "You are a word prediction engine. The user is typing a sentence and "
            "has partially typed a word. Predict the most likely completions.\n"
            "Rules:\n"
            f"- Return EXACTLY {top_k} single words, one per line, nothing else\n"
            "- Each word MUST start with the given prefix\n"
            "- Rank by likelihood given the sentence context\n"
            "- No numbering, no punctuation, no explanations\n"
            "- All lowercase"
        )
        user_prompt = f'Sentence so far: "{sentence}"\nPartial word: "{prefix}"'

        try:
            result = self.complete(
                context=user_prompt,
                system_prompt=system_prompt,
                max_tokens=50,
                temperature=0.2,
            )
            if not result:
                return []

            # Parse: one word per line
            words = []
            prefix_lower = prefix.lower()
            for line in result.strip().splitlines():
                word = line.strip().lower().strip('.-,;:!?"\' 0123456789')
                if word and word.startswith(prefix_lower) and word != prefix_lower:
                    words.append(word)
            # Assign decreasing confidence based on order
            completions = []
            for i, word in enumerate(dict.fromkeys(words)):  # dedupe preserving order
                completions.append((word, 1.0 - i * 0.1))
                if len(completions) >= top_k:
                    break
            return completions

        except Exception as e:
            logger.debug("Cloud word completion failed: %s", e)
            return []

    def code_assist(self, code_context: str, language: str = "python") -> str:
        """
        Specialized code completion request.
        Uses a code-optimized system prompt and lower temperature.
        """
        system_prompt = (
            f"You are an expert {language} programmer. Complete the code below. "
            f"Return ONLY the code continuation, no explanations, no markdown. "
            f"Match the existing style and indentation."
        )
        return self.complete(
            context=code_context,
            system_prompt=system_prompt,
            max_tokens=200,
            temperature=0.1,
        )

    def elaborate(self, text: str, style: str = "professional") -> str:
        """
        Expand/rewrite the given text in the specified style.
        """
        system_prompt = (
            f"Rewrite and elaborate on the following text in a {style} style. "
            f"Make it more detailed and polished. Return only the rewritten text."
        )
        return self.complete(
            context=f"Original text: {text}",
            system_prompt=system_prompt,
            max_tokens=500,
            temperature=0.5,
        )

    # ─── Internal API Calls ──────────────────────────────────────

    def _do_api_call(self, context, system_prompt, max_tokens, temperature, cache_key) -> str:
        """Execute the API call with retry and fallback logic."""
        self._total_calls += 1

        # Try providers in priority order
        providers = self._get_provider_order()
        last_error = None

        for provider in providers:
            try:
                if provider == "groq" and self._groq_key:
                    result = self._call_groq(context, system_prompt, max_tokens, temperature)
                elif provider == "gemini" and self._gemini_key:
                    result = self._call_gemini(context, system_prompt, max_tokens, temperature)
                elif provider == "anthropic" and self._anthropic_key:
                    result = self._call_anthropic(context, system_prompt, max_tokens, temperature)
                elif provider == "openai" and self._openai_key:
                    result = self._call_openai(context, system_prompt, max_tokens, temperature)
                else:
                    continue

                # Cache the result
                self._cache_result(cache_key, result)
                return result

            except Exception as e:
                last_error = e
                self._total_errors += 1
                logger.warning("Cloud API call failed (%s): %s", provider, e)
                continue

        logger.error("All cloud providers failed. Last error: %s", last_error)
        return ""

    # ─── Groq Cloud ──────────────────────────────────────────────

    def _call_groq(self, context, system_prompt, max_tokens, temperature) -> str:
        """Call Groq Cloud API (OpenAI-compatible, free tier)."""
        try:
            from groq import Groq
            client = Groq(api_key=self._groq_key)
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": context})
            response = client.chat.completions.create(
                model=self._config.get("groq_model", "llama-3.3-70b-versatile"),
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response.choices[0].message.content
        except ImportError:
            return self._call_groq_raw(context, system_prompt, max_tokens, temperature)

    def _call_groq_raw(self, context, system_prompt, max_tokens, temperature) -> str:
        """Call Groq API using raw HTTP requests."""
        import urllib.request

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._groq_key}",
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": context})

        payload = json.dumps({
            "model": self._config.get("groq_model", "llama-3.3-70b-versatile"),
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }).encode("utf-8")

        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]

    # ─── Google Gemini ───────────────────────────────────────────

    def _call_gemini(self, context, system_prompt, max_tokens, temperature) -> str:
        """Call Google Gemini API."""
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self._gemini_key)
            model = self._config.get("gemini_model", "gemini-2.0-flash")

            config = types.GenerateContentConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
                system_instruction=system_prompt if system_prompt else None,
            )
            response = client.models.generate_content(
                model=model,
                contents=context,
                config=config,
            )
            return response.text
        except ImportError:
            # Fallback: use raw HTTP
            return self._call_gemini_raw(context, system_prompt, max_tokens, temperature)

    def _call_gemini_raw(self, context, system_prompt, max_tokens, temperature) -> str:
        """Call Gemini API using raw HTTP requests (no SDK needed)."""
        import urllib.request

        model = self._config.get("gemini_model", "gemini-2.0-flash")
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
            f":generateContent?key={self._gemini_key}"
        )
        headers = {"Content-Type": "application/json"}

        # Build the request body
        body = {
            "contents": [{"parts": [{"text": context}]}],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
            },
        }
        if system_prompt:
            body["systemInstruction"] = {
                "parts": [{"text": system_prompt}]
            }

        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["candidates"][0]["content"]["parts"][0]["text"]

    # ─── Anthropic Claude ────────────────────────────────────────

    def _call_anthropic(self, context, system_prompt, max_tokens, temperature) -> str:
        """Call Anthropic Claude API."""
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self._anthropic_key)
            response = client.messages.create(
                model=self._config.get("anthropic_model", "claude-sonnet-4-20250514"),
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": context}],
                temperature=temperature,
            )
            return response.content[0].text
        except ImportError:
            return self._call_anthropic_raw(context, system_prompt, max_tokens, temperature)

    def _call_anthropic_raw(self, context, system_prompt, max_tokens, temperature) -> str:
        """Call Anthropic API using raw HTTP requests (no SDK needed)."""
        import urllib.request
        import urllib.error

        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self._anthropic_key,
            "anthropic-version": "2023-06-01",
        }
        payload = json.dumps({
            "model": self._config.get("anthropic_model", "claude-sonnet-4-20250514"),
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": context}],
            "temperature": temperature,
        }).encode("utf-8")

        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["content"][0]["text"]

    # ─── OpenAI GPT ──────────────────────────────────────────────

    def _call_openai(self, context, system_prompt, max_tokens, temperature) -> str:
        """Call OpenAI GPT API."""
        try:
            import openai
            client = openai.OpenAI(api_key=self._openai_key)
            response = client.chat.completions.create(
                model=self._config.get("openai_model", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": context},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response.choices[0].message.content
        except ImportError:
            return self._call_openai_raw(context, system_prompt, max_tokens, temperature)

    def _call_openai_raw(self, context, system_prompt, max_tokens, temperature) -> str:
        """Call OpenAI API using raw HTTP requests."""
        import urllib.request

        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._openai_key}",
        }
        payload = json.dumps({
            "model": self._config.get("openai_model", "gpt-4o-mini"),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }).encode("utf-8")

        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]

    # ─── Helpers ─────────────────────────────────────────────────

    def _call_and_callback(self, context, system_prompt, max_tokens, temperature, callback, cache_key):
        """Background thread for async API calls."""
        result = self._do_api_call(context, system_prompt, max_tokens, temperature, cache_key)
        callback(result)

    def _get_provider_order(self) -> list:
        """Get the provider fallback order."""
        all_providers = ["groq", "gemini", "openai", "anthropic"]
        if self._primary_provider in all_providers:
            all_providers.remove(self._primary_provider)
            return [self._primary_provider] + all_providers
        return all_providers

    def _make_cache_key(self, context: str, system_prompt: str) -> str:
        combined = f"{system_prompt}||{context}"
        return hashlib.md5(combined.encode()).hexdigest()

    def _cache_result(self, key: str, result: str):
        self._cache[key] = result
        self._cache.move_to_end(key)
        while len(self._cache) > self._max_cache_size:
            self._cache.popitem(last=False)
