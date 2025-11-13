#!/usr/bin/env python3
"""Legacy wrapper for evaluate_adaptive_predictor.

Retained for backward compatibility with existing automation.
"""

import warnings

warnings.warn(
    "evaluate_simple_predictor.py is deprecated; use evaluate_adaptive_predictor.py",
    DeprecationWarning,
    stacklevel=2,
)

from evaluate_adaptive_predictor import *  # noqa: F401,F403
