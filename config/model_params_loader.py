"""Utility for loading tuned model parameters.

Centralizes reading of `model_params.json` so pipeline, tuner, and other
components can share consistent behavior (graceful fallback on errors).
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

def load_model_params(path: str | None = None) -> Dict[str, Any]:
    """Load model params JSON.

    Parameters
    ----------
    path : Optional[str]
        Explicit path to params JSON. If omitted, resolves relative to this
        module directory (`config/model_params.json`).

    Returns
    -------
    Dict[str, Any]
        Parsed JSON dict or empty dict on any failure.
    """
    if path is None:
        path = os.path.join(os.path.dirname(__file__), 'model_params.json')
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception:
        return {}

__all__ = ["load_model_params"]
