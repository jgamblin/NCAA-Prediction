import os
import sys

# Ensure repository root on path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from data_collection.team_name_utils import normalize_team_name  # noqa: E402


def test_penn_vs_penn_state_distinct():
    assert normalize_team_name("Penn Quakers") == "Penn"
    assert normalize_team_name("Penn State Nittany Lions") == "Penn State"
    # Plain forms should remain unchanged
    assert normalize_team_name("Penn") == "Penn"
    assert normalize_team_name("Penn State") == "Penn State"
    # Ensure no accidental cross-mapping
    assert normalize_team_name("Penn State Quakers") == "Penn State Quakers"  # nonsensical hybrid should pass through
    assert normalize_team_name("Penn Nittany Lions") == "Penn Nittany Lions"  # likewise
