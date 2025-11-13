#!/usr/bin/env python3
"""Legacy wrapper for quick_adaptive_predictions.

Retained for backwards compatibility. Prefer running
``python quick_adaptive_predictions.py`` instead.
"""

import warnings

warnings.warn(
    "quick_simple_predictions.py is deprecated; use quick_adaptive_predictions.py",
    DeprecationWarning,
    stacklevel=2,
)

from quick_adaptive_predictions import *  # noqa: F401,F403
