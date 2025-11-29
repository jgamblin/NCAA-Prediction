# 🧹 Repository Cleanup & Refactoring Plan

_Created: November 29, 2025_

This document outlines a comprehensive plan to clean up the NCAA-Prediction repository, remove unused files, consolidate redundant code, and make the pipeline bulletproof.

---

## Executive Summary

### Current State
- **83 Python files** across the repository
- **41 data CSV files** in `/data`
- Multiple legacy/deprecated files still present
- Some redundant implementations (v1 vs v2, simple vs adaptive)
- GitHub Actions could be more robust with better error handling

### Goals
1. Remove unused and deprecated files
2. Consolidate redundant implementations
3. Improve pipeline reliability and error handling
4. Simplify directory structure
5. Update documentation to reflect changes

---

## Phase 1: File Cleanup (Safe Deletions)

### 1.1 Deprecated/Unused Python Files to DELETE

| File | Reason | Confidence |
|------|--------|------------|
| `model_training/ncaa_predictions.py` | Legacy v1 implementation, not imported anywhere | ✅ High |
| `model_training/run_predictions.py` | Only imports from ncaa_predictions_v2, can be inlined | ✅ High |
| `model_training/simple_predictor.py` | Just a shim to AdaptivePredictor (alias exists in adaptive_predictor.py) | ✅ High |
| `game_prediction/quick_simple_predictions.py` | Shim that imports quick_adaptive_predictions | ✅ High |
| `game_prediction/view_predictions.py` | Standalone utility, not used in pipeline | ⚠️ Medium |
| `game_prediction/add_demo_moneylines.py` | Demo/testing utility, not used in production | ⚠️ Medium |
| `game_prediction/backfill_season_bets.py` | One-time backfill script | ⚠️ Medium |
| `scripts/debug_indiana_prediction.py` | Debug script, issue resolved | ✅ High |
| `scripts/archive/check_team_ids.py` | Already archived, safe to delete | ✅ High |
| `model_training/anomaly_trends.py` | Not imported anywhere | ⚠️ Medium |
| `model_training/conference_drift.py` | Not imported in pipeline | ⚠️ Medium |
| `tests/test_simple_predictor_smoke.py` | Already skipped, deprecated | ✅ High |

### 1.2 Data Collection Scripts - Review Needed

| File | Status | Action |
|------|--------|--------|
| `data_collection/all_games.py` | Used by backfill_missing_d1.py, collect_data.py | ✅ KEEP |
| `data_collection/backfill_missing_d1.py` | Used for historical backfill | ✅ KEEP |
| `data_collection/build_espn_alias_map.py` | Utility script, rarely used | ⚠️ ARCHIVE |
| `data_collection/build_id_lookup.py` | Used optionally in pipeline | ✅ KEEP |
| `data_collection/check_conference_coverage.py` | Used by conference_drift.py | ⚠️ REVIEW |
| `data_collection/check_d1_coverage.py` | Utility script | ⚠️ ARCHIVE |
| `data_collection/check_seasons.py` | Utility script | ⚠️ ARCHIVE |
| `data_collection/check_unmatched_teams.py` | Utility script | ⚠️ ARCHIVE |
| `data_collection/collect_data.py` | Historical data collection | ⚠️ ARCHIVE |
| `data_collection/filter_to_d1.py` | Data processing utility | ✅ KEEP |
| `data_collection/regenerate_completed_games.py` | Maintenance utility | ⚠️ ARCHIVE |

### 1.3 Game Prediction Scripts - Review Needed

| File | Status | Action |
|------|--------|--------|
| `game_prediction/betting_tracker.py` | Used in pipeline | ✅ KEEP |
| `game_prediction/generate_predictions_md.py` | Used in pipeline | ✅ KEEP |
| `game_prediction/track_accuracy.py` | Used in pipeline | ✅ KEEP |
| `game_prediction/update_readme_stats.py` | Used in pipeline | ✅ KEEP |
| `game_prediction/publish_artifacts.py` | Used in pipeline | ✅ KEEP |
| `game_prediction/calculate_streak.py` | Used in pipeline | ✅ KEEP |
| `game_prediction/quick_adaptive_predictions.py` | Standalone utility | ⚠️ REVIEW |
| `game_prediction/analyze_betting_lines.py` | Analysis utility | ⚠️ ARCHIVE |
| `game_prediction/backfill_moneylines.py` | One-time backfill | ⚠️ ARCHIVE |

### 1.4 Documentation Cleanup

| File | Action | Reason |
|------|--------|--------|
| `docs/EXTRA_NON_D1_TEAMS_WITH_COUNTS.txt` | DELETE | One-time analysis output |
| `docs/TEAM_NAME_BUG_ANALYSIS.md` | ARCHIVE | Historical bug analysis |
| `docs/INVESTIGATION_RESULTS.md` | ARCHIVE | Historical investigation |
| `docs/ID_MIGRATION.md` | ARCHIVE | Completed migration docs |

### 1.5 Data Files Cleanup

| File | Action | Reason |
|------|--------|--------|
| `data/evaluation/*.csv` | REVIEW | May be stale evaluation data |
| `data_collection/data/ESPN_Current_Season.csv` | DELETE | Duplicate location for data |
| `data/Completed_Games_Normalized.csv` | REVIEW | May be intermediate file |
| `data/Simple_Feature_Importance.csv` | DELETE | Legacy from simple predictor |

---

## Phase 2: Code Consolidation

### 2.1 Merge ncaa_predictions_v2.py Functions

The `ncaa_predictions_v2.py` file contains utility functions used by tests. Options:
1. Move `calibration_report()` and `extract_fs_feature_importance()` to appropriate modules
2. Keep file but rename to `prediction_utils.py`

**Recommendation:** Rename to `prediction_utils.py` and document its purpose.

### 2.2 Consolidate Predictor Classes

Current state:
- `AdaptivePredictor` in `adaptive_predictor.py` - main implementation
- `SimplePredictor` alias in same file
- `simple_predictor.py` - just imports AdaptivePredictor

**Action:** Delete `simple_predictor.py`, keep alias in `adaptive_predictor.py`

### 2.3 Consolidate Quick Prediction Scripts

Current state:
- `quick_adaptive_predictions.py` - actual implementation
- `quick_simple_predictions.py` - imports from quick_adaptive

**Action:** Delete `quick_simple_predictions.py`

---

## Phase 3: Pipeline Hardening

### 3.1 Daily Pipeline Improvements (`daily_pipeline.py`)

```python
# Current issues:
# 1. No retry logic for ESPN scraping
# 2. Limited error handling
# 3. No health checks
# 4. Missing data validation

# Proposed improvements:
```

#### 3.1.1 Add Retry Logic for ESPN Scraping
```python
import time
from functools import wraps

def retry_on_failure(max_retries=3, delay=5):
    """Decorator to retry failed operations."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        print(f"  Attempt {attempt + 1} failed: {e}")
                        print(f"  Retrying in {delay} seconds...")
                        time.sleep(delay)
            raise last_exception
        return wrapper
    return decorator
```

#### 3.1.2 Add Data Validation
```python
def validate_dataframe(df, name, required_cols, min_rows=1):
    """Validate DataFrame has required columns and minimum rows."""
    missing = set(required_cols) - set(df.columns)
    if missing:
        raise ValueError(f"{name} missing columns: {missing}")
    if len(df) < min_rows:
        raise ValueError(f"{name} has {len(df)} rows, expected >= {min_rows}")
    return True
```

#### 3.1.3 Add Pipeline Health Summary
```python
def generate_health_report():
    """Generate pipeline health report."""
    return {
        'timestamp': datetime.now().isoformat(),
        'games_scraped': len(games),
        'predictions_made': len(predictions),
        'accuracy_tracked': accuracy_count,
        'errors': error_list,
        'status': 'healthy' if not error_list else 'degraded'
    }
```

### 3.2 GitHub Actions Improvements

#### 3.2.1 Daily Predictions Workflow Enhancements

```yaml
# Proposed changes to daily-predictions.yml:

jobs:
  update-predictions:
    runs-on: ubuntu-latest
    timeout-minutes: 30  # ADD: Prevent hanging jobs
    
    steps:
    # ADD: Cache pip dependencies
    - name: Cache pip packages
      uses: actions/cache@v4
      with:
        path: ~/.cache/pip
        key: ${{ runner.os }}-pip-${{ hashFiles('requirements.txt') }}
        restore-keys: |
          ${{ runner.os }}-pip-
    
    # ADD: Validate data files exist
    - name: Validate data files
      run: |
        for file in data/Completed_Games.csv data/Upcoming_Games.csv; do
          if [ ! -f "$file" ]; then
            echo "Missing required file: $file"
            exit 1
          fi
        done
    
    # ADD: Run tests before pipeline
    - name: Run critical tests
      run: |
        python -m pytest tests/test_adaptive_predictor_smoke.py -v --tb=short
    
    # MODIFY: Better error handling
    - name: Run daily pipeline
      id: pipeline
      run: |
        set -o pipefail
        python3 daily_pipeline.py 2>&1 | tee pipeline.log
      continue-on-error: true
    
    # ADD: Upload logs on failure
    - name: Upload pipeline logs
      if: failure()
      uses: actions/upload-artifact@v4
      with:
        name: pipeline-logs
        path: pipeline.log
        retention-days: 7
    
    # ADD: Notify on failure (optional)
    - name: Check pipeline status
      if: steps.pipeline.outcome == 'failure'
      run: |
        echo "::error::Daily pipeline failed. Check logs for details."
        exit 1
```

#### 3.2.2 Weekly Tuning Workflow Enhancements

```yaml
# Proposed changes to weekly-tuning.yml:

jobs:
  tune-model:
    runs-on: ubuntu-latest
    timeout-minutes: 60  # ADD: Tuning can take longer
    
    steps:
    # ADD: Backup current model params before tuning
    - name: Backup model params
      run: |
        cp config/model_params.json config/model_params.backup.json
    
    # ADD: Validate tuning results
    - name: Validate tuning output
      if: steps.data_check.outputs.tune_needed == 'true'
      run: |
        python -c "
        import json
        with open('config/model_params.json') as f:
            params = json.load(f)
        assert 'n_estimators' in params, 'Missing n_estimators'
        assert 'max_depth' in params, 'Missing max_depth'
        print('Model params validated successfully')
        "
    
    # ADD: Rollback on validation failure
    - name: Rollback on failure
      if: failure()
      run: |
        if [ -f config/model_params.backup.json ]; then
          cp config/model_params.backup.json config/model_params.json
          echo "Rolled back to previous model params"
        fi
```

### 3.3 Add Pre-commit Hooks

Create `.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-added-large-files
        args: ['--maxkb=1000']
  
  - repo: https://github.com/psf/black
    rev: 24.3.0
    hooks:
      - id: black
        args: ['--line-length=100']
  
  - repo: https://github.com/pycqa/isort
    rev: 5.13.2
    hooks:
      - id: isort
        args: ['--profile=black']
```

---

## Phase 4: Directory Structure Reorganization

### 4.1 Proposed New Structure

```
NCAA-Prediction/
├── .github/
│   └── workflows/
│       ├── daily-predictions.yml
│       └── weekly-tuning.yml
├── config/
│   ├── feature_flags.json
│   ├── model_params.json
│   └── settings.yaml
├── data/
│   ├── raw/                    # Raw scraped data
│   ├── processed/              # Processed/cleaned data
│   ├── predictions/            # Prediction outputs
│   └── evaluation/             # Evaluation metrics
├── src/                        # RENAME from scattered modules
│   ├── data_collection/
│   ├── model/                  # RENAME from model_training
│   ├── prediction/             # RENAME from game_prediction
│   └── utils/
├── scripts/                    # Utility/maintenance scripts
│   └── archive/                # Deprecated scripts
├── tests/
├── docs/
│   ├── archive/                # Historical docs
│   └── performance/
├── daily_pipeline.py
├── requirements.txt
└── README.md
```

**Note:** This is a significant change. Consider implementing incrementally.

---

## Phase 5: Implementation Order

### Week 1: Safe Deletions
1. ✅ Delete `model_training/ncaa_predictions.py`
2. ✅ Delete `model_training/simple_predictor.py`
3. ✅ Delete `game_prediction/quick_simple_predictions.py`
4. ✅ Delete `scripts/debug_indiana_prediction.py`
5. ✅ Delete `scripts/archive/check_team_ids.py`
6. ✅ Delete `tests/test_simple_predictor_smoke.py`
7. ✅ Delete `data_collection/data/ESPN_Current_Season.csv`

### Week 2: Archive Utilities
1. Create `scripts/archive/` folder for deprecated utilities
2. Move rarely-used data collection scripts to archive
3. Move one-time backfill scripts to archive
4. Update imports if any exist

### Week 3: Pipeline Hardening
1. Add retry logic to daily_pipeline.py
2. Add data validation
3. Update GitHub Actions with timeout, caching, error handling
4. Add pipeline health reporting

### Week 4: Final Cleanup
1. Rename `ncaa_predictions_v2.py` → `prediction_utils.py`
2. Clean up documentation
3. Update README with new structure
4. Run full test suite
5. Create release notes

---

## Testing Strategy

### Before Any Deletion
```bash
# Run full test suite
python -m pytest tests/ -v

# Run pipeline in dry-run mode (if available)
python daily_pipeline.py --dry-run

# Check for import errors
python -c "from daily_pipeline import main; print('Import OK')"
```

### After Each Phase
```bash
# Verify all tests pass
python -m pytest tests/ -v --tb=short

# Verify pipeline still works
python daily_pipeline.py

# Check for broken imports
find . -name "*.py" -exec python -c "import ast; ast.parse(open('{}').read())" \;
```

---

## Risk Assessment

| Change | Risk | Mitigation |
|--------|------|------------|
| Delete legacy files | Low | Files are not imported |
| Pipeline hardening | Low | Additive changes only |
| Rename files | Medium | Update all imports, run tests |
| Directory restructure | High | Do incrementally, extensive testing |

---

## Rollback Plan

1. **Git tags:** Create tag before each phase
   ```bash
   git tag pre-cleanup-phase1
   ```

2. **Backup branch:**
   ```bash
   git checkout -b backup/pre-cleanup
   ```

3. **Revert commits:**
   ```bash
   git revert HEAD~N..HEAD  # Revert last N commits
   ```

---

## Success Criteria

- [ ] All tests pass (100+ tests)
- [ ] Daily pipeline runs successfully
- [ ] Weekly tuning runs successfully
- [ ] No import errors
- [ ] Code coverage maintained or improved
- [ ] Repository size reduced
- [ ] Documentation updated

---

## Appendix: Files to Keep (Core Pipeline)

### Essential Files
```
daily_pipeline.py                    # Main entry point
config/feature_flags.json            # Feature toggles
config/model_params.json             # Model configuration
config/settings.yaml                 # General settings
config/load_config.py                # Config loader
config/versioning.py                 # Version tracking
data_collection/espn_scraper.py      # Data collection
data_collection/team_name_utils.py   # Team normalization
model_training/adaptive_predictor.py # Main predictor
model_training/power_ratings.py      # Phase 2 features
model_training/home_away_splits.py   # Phase 2 features
model_training/conference_strength.py # Phase 4 features
model_training/recency_weighting.py  # Phase 4 features
model_training/ensemble_predictor.py # Phase 3 ensemble
model_training/feature_store.py      # Feature management
model_training/drift_monitor.py      # Model monitoring
model_training/team_drift_monitor.py # Team monitoring
game_prediction/betting_tracker.py   # Betting analysis
game_prediction/track_accuracy.py    # Accuracy tracking
game_prediction/generate_predictions_md.py # Output generation
```
