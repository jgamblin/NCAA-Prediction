"""Versioning utilities: provide git commit hash for lineage embedding."""
from __future__ import annotations
import subprocess

def get_commit_hash(short: bool = True) -> str:
    try:
        args = ['git','rev-parse','--short','HEAD'] if short else ['git','rev-parse','HEAD']
        result = subprocess.run(args, capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return 'unknown'
