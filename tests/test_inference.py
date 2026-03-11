"""Tests for the Inference Engine."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from inference.decision_logic import (
    DecisionLogic, InferenceRequest, RequestType, InferencePath
)
from inference.local_engine import LocalEngine
from inference.engine import HybridInferenceEngine
from src.autocorrect import AutoCorrector, Dictionary
from src.prediction import NGramModel


class TestDecisionLogic:
    """Tests for inference routing logic."""

    def test_next_word_always_local(self):
        dl = DecisionLogic()
        req = InferenceRequest(
            request_type=RequestType.NEXT_WORD,
            context="hello world",
        )
        assert dl.decide(req) == InferencePath.LOCAL

    def test_autocorrect_always_local(self):
        dl = DecisionLogic()
        req = InferenceRequest(
            request_type=RequestType.AUTOCORRECT,
            context="hello",
            current_word="helo",
        )
        assert dl.decide(req) == InferencePath.LOCAL

    def test_code_assist_goes_cloud(self):
        dl = DecisionLogic(cloud_available=True)
        req = InferenceRequest(
            request_type=RequestType.CODE_ASSIST,
            context="def hello():",
            context_mode="code",
        )
        assert dl.decide(req) == InferencePath.CLOUD

    def test_offline_mode_forces_local(self):
        dl = DecisionLogic(offline_only=True)
        req = InferenceRequest(
            request_type=RequestType.CODE_ASSIST,
            context="def hello():",
            context_mode="code",
        )
        assert dl.decide(req) == InferencePath.LOCAL

    def test_circuit_breaker(self):
        dl = DecisionLogic()
        # Simulate 3 failures
        for _ in range(3):
            dl.report_cloud_failure()
        req = InferenceRequest(
            request_type=RequestType.ELABORATE,
            context="test text",
        )
        # Should fall back to local after circuit breaker opens
        assert dl.decide(req) == InferencePath.LOCAL

    def test_system_prompt_code_mode(self):
        dl = DecisionLogic()
        prompt = dl.get_system_prompt("code")
        assert "programming" in prompt.lower() or "code" in prompt.lower()

    def test_system_prompt_general_mode(self):
        dl = DecisionLogic()
        prompt = dl.get_system_prompt("general")
        assert "typing assistant" in prompt.lower() or "helpful" in prompt.lower()


class TestLocalEngine:
    """Tests for the local inference engine."""

    def test_ngram_prediction(self):
        engine = LocalEngine()
        model = NGramModel(n=2)
        model.train("the cat sat on the mat")
        dictionary = Dictionary()
        engine.initialize(dictionary=dictionary, ngram_model=model)

        predictions = engine.predict_next_word("the", top_k=3)
        assert len(predictions) > 0

    def test_autocorrect(self):
        engine = LocalEngine()
        dictionary = Dictionary()
        corrector = AutoCorrector(dictionary=dictionary)
        engine.initialize(dictionary=dictionary, autocorrector=corrector)

        result = engine.autocorrect("helo")
        assert result == "hello"

    def test_engine_ready(self):
        engine = LocalEngine()
        assert not engine.is_ready
        engine.initialize()
        assert engine.is_ready


class TestHybridEngine:
    """Tests for the hybrid inference engine."""

    def test_local_prediction(self):
        engine = HybridInferenceEngine()
        model = NGramModel(n=2)
        model.train("hello world hello world hello world")
        engine.initialize(ngram_model=model)

        req = InferenceRequest(
            request_type=RequestType.NEXT_WORD,
            context="hello",
        )
        result = engine.infer(req)
        assert result.source == InferencePath.LOCAL
        assert result.latency_ms >= 0

    def test_stats_tracking(self):
        engine = HybridInferenceEngine()
        engine.initialize()

        req = InferenceRequest(
            request_type=RequestType.NEXT_WORD,
            context="test",
        )
        engine.infer(req)
        assert engine.total_requests == 1
        assert engine.local_requests == 1
