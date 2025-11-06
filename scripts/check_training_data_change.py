#!/usr/bin/env python3
"""Emit whether model tuning is needed based on file content hashes.

Outputs lines suitable for GitHub Actions $GITHUB_OUTPUT consumption:
  tune_needed=true|false
  tune_reasons=<comma separated reasons>

Logic:
- If Model_Tuning_Log.json absent => tune.
- Compute MD5 for Completed_Games.csv, Completed_Games_Normalized.csv, feature_store.csv, model_params.json.
- Compare to last log entry hash fields; if any differ => tune.
- If last_tuned older than 7 days => tune.
- If normalized file newly appears or disappears => tune.
- Always tune if feature store diff feature count increased.
"""
from __future__ import annotations
import os, json, hashlib, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
CONFIG = os.path.join(ROOT, 'config')
LOG_PATH = os.path.join(DATA, 'Model_Tuning_Log.json')
FS_PATH = os.path.join(DATA, 'feature_store', 'feature_store.csv')
COMPLETED = os.path.join(DATA, 'Completed_Games.csv')
NORMALIZED = os.path.join(DATA, 'Completed_Games_Normalized.csv')
PARAMS = os.path.join(CONFIG, 'model_params.json')

TARGETS = {
    'completed_games_md5': COMPLETED,
    'normalized_games_md5': NORMALIZED,
    'feature_store_md5': FS_PATH,
    'model_params_md5': PARAMS,
}

def md5(path: str) -> str | None:
    if not os.path.exists(path):
        return None
    try:
        h = hashlib.md5()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None

current_hashes = {k: md5(p) for k, p in TARGETS.items()}
reasons: list[str] = []
needs_tune = False

if not os.path.exists(LOG_PATH):
    needs_tune = True
    reasons.append('no_tuning_log')
    last_entry = None
else:
    try:
        with open(LOG_PATH) as f:
            log = json.load(f)
        if isinstance(log, list) and log:
            last_entry = log[-1]
        else:
            last_entry = None
    except Exception:
        last_entry = None
        needs_tune = True
        reasons.append('log_read_error')

if last_entry:
    # Age check
    try:
        ts = datetime.datetime.strptime(last_entry.get('date', ''), '%Y-%m-%d %H:%M:%S')
        if (datetime.datetime.utcnow() - ts).days >= 7:
            needs_tune = True
            reasons.append('last_run_>=7days')
    except Exception:
        needs_tune = True
        reasons.append('timestamp_parse_fail')
    # Hash comparison
    for field, value in current_hashes.items():
        prev = last_entry.get(field)
        if prev != value:
            needs_tune = True
            reason = f"changed:{field}" if prev is not None else f"new:{field}"
            reasons.append(reason)
    # Normalized file presence change
    prev_norm = last_entry.get('normalized_games_md5') is not None
    now_norm = current_hashes.get('normalized_games_md5') is not None
    if prev_norm != now_norm:
        needs_tune = True
        reasons.append('normalized_presence_change')
    # Feature store diff feature count change
    prev_fs_count = last_entry.get('fs_diff_feature_count')
    # Crude re-derivation: count columns containing '_diff' in feature_store if exists
    fs_diff_count_now = 0
    if os.path.exists(FS_PATH):
        import pandas as pd
        try:
            fs_df = pd.read_csv(FS_PATH, nrows=5)
            fs_diff_count_now = len([c for c in fs_df.columns if c.endswith('_diff')])
        except Exception:
            pass
    if prev_fs_count != fs_diff_count_now:
        needs_tune = True
        reasons.append('fs_diff_feature_count_change')
else:
    # No previous entry: already flagged
    pass

# Emit outputs
print(f"tune_needed={'true' if needs_tune else 'false'}")
print(f"tune_reasons={','.join(reasons) if reasons else 'none'}")
