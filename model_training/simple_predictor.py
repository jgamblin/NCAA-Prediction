"""Compatibility shim for legacy SimplePredictor imports.

The main implementation now lives in ``adaptive_predictor.py``.
"""

from adaptive_predictor import AdaptivePredictor

SimplePredictor = AdaptivePredictor

__all__ = ["SimplePredictor", "AdaptivePredictor"]
