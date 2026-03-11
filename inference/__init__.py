"""
Desktop G-Board — Inference Module
====================================
Hybrid inference engine with local and cloud paths.
"""

from .decision_logic import DecisionLogic, InferenceRequest, InferenceResult
from .local_engine import LocalEngine
from .cloud_engine import CloudEngine
from .engine import HybridInferenceEngine

__all__ = [
    "HybridInferenceEngine",
    "DecisionLogic",
    "InferenceRequest",
    "InferenceResult",
    "LocalEngine",
    "CloudEngine",
]
