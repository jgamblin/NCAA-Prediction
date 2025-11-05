"""Configuration loader for NCAA Prediction pipeline.

Reads YAML settings from config/settings.yaml and provides a dict-like interface.
Falls back to sane defaults if file missing or malformed.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Any, Dict
import hashlib

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # Minimal fallback

DEFAULTS: Dict[str, Any] = {
    'row_inflation_guard_pct': 0.10,
    'anomaly_accuracy_delta_threshold': 0.25,
    'anomaly_min_games': 15,
    'calibration_bins': 10,
    'team_drift_window': 25,
    'id_refresh_enabled_default': False,
}

CONFIG_PATH = Path(__file__).parent / 'settings.yaml'

_cache: Dict[str, Any] | None = None


def _compute_version(path: Path) -> str:
    try:
        data = path.read_bytes()
        return hashlib.sha1(data).hexdigest()[:12]
    except Exception:
        return "unknown"


def get_config(refresh: bool = False) -> Dict[str, Any]:
    global _cache
    if _cache is not None and not refresh:
        return _cache
    cfg = DEFAULTS.copy()
    if CONFIG_PATH.exists() and yaml is not None:
        try:
            with open(CONFIG_PATH, 'r') as f:
                loaded = yaml.safe_load(f) or {}
            if isinstance(loaded, dict):
                for k, v in loaded.items():
                    cfg[k] = v
        except Exception as e:  # pragma: no cover
            print(f"⚠️ Failed to load config/settings.yaml, using defaults: {e}")
    cfg['config_version'] = _compute_version(CONFIG_PATH) if CONFIG_PATH.exists() else 'defaults'
    _cache = cfg
    return cfg

def get_config_version() -> str:
    return get_config().get('config_version','unknown')

__all__ = ['get_config','get_config_version']
