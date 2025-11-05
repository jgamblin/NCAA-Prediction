# ID Migration & Per-Team Enhancements

This document tracks the transition from name-based processing to stable `team_id` keyed logic.

## Goals
1. Drift monitoring keyed by `team_id` (per-team performance trajectories).
2. Persisted per-team feature store for fast model inference.
3. Cross-source reconciliation (KenPom / NCAA / ESPN) via a unified lookup map.

## Components Added

| File | Purpose |
|------|---------|
| `model_training/team_id_utils.py` | Deterministic fallback ID derivation & melting games to team perspective rows. |
| `model_training/team_drift_monitor.py` | Per-team drift metrics computation. |
| `model_training/feature_store.py` | Rolling per-team feature aggregation cache. |
| `data_collection/id_mapping.py` | Stub for cross-source ID reconciliation loader. |
| `data/feature_store/feature_store.csv` | Persisted feature store (created on first build). |
| `Drift_Metrics_By_Team.csv` / `DRIFT_METRICS_BY_TEAM.md` | Output per-team drift metrics. |

## Deterministic Fallback IDs
Historical data lacks numeric IDs for many seasons. We generate stable IDs:
```
name_<12 hex chars of SHA1(normalized_lower_name)>
```
Collision probability is negligible for ~1000 teams.

## Per-Team Drift Metrics
We mirror global metrics but from each team’s perspective:
- `cumulative_accuracy_team`: Probability threshold accuracy (>=0.5) given available predictions.
- `cumulative_logloss_team`, `cumulative_brier_team`: Standard calibration metrics.
- Rolling variants over `--window` (default 25).
- Expected vs actual wins accumulation to surface over/under-performance.

## Feature Store
Initial features (for each season+team_id):
- Rolling win pct last 5 & 10 games.
- Rolling average point differential (last 5 & 10).
- Games played.

These features can be merged into prediction pipelines before model inference to reduce recomputation.

## ID Lookup (Cross-Source)
`data/id_lookup.csv` (not yet populated) will hold columns:
```
canonical_name, espn_id, kenpom_name, kenpom_id, ncaa_name, ncaa_id
```
A stub builder (`build_minimal_espn_lookup`) can seed ESPN pairs from scraped game data; future enrichment will add KenPom & NCAA IDs.

## Next Steps
- Populate `data/id_lookup.csv` with ESPN IDs where available.
- Add integration to prediction training to merge feature store features.
- Extend drift monitor to flag anomalous per-team changes (e.g., sudden logloss spike).
- Add KenPom/NCAA ingestion scripts to fill missing IDs.
- Unit tests for `id_mapping.resolve_any` and feature store incremental updates.

### (Progress Update)
Implemented:
- Pipeline feature store build & enrichment of upcoming games (`daily_pipeline.py` step 2.5).
- Anomaly detection producing `data/Team_Anomalies.csv` (heuristic delta accuracy threshold).
- Initial ID lookup builder script: `data_collection/build_id_lookup.py`.
- Feature store tests (`tests/test_feature_store.py`).

Season-Aware Join Note:
Early integration briefly merged feature store rows only by `team_id`, which created a cartesian expansion (multiple historical seasons per team). The pipeline now merges on `(team_id, season)` and reduces the feature store to the latest row per team-season (highest `games_played`) to maintain a 1:1 relationship with game rows.

Planned Enhancements:
- Incorporate feature store fields into model feature engineering (difference metrics, cold streak signals).
- Add CLI to regenerate anomalies markdown summary.
- Expand lookup with KenPom & NCAA sources once data ingestion scripts are added.

## Testing
Add tests to verify:
- Deterministic ID generation stability across runs.
- Correct melting of home/away into per-team rows.
- Rolling feature calculations for edge window sizes.

## Migration Notes
No breaking changes to existing global drift workflow. New modules are additive. Downstream code should progressively switch from name matching to `team_id` usage for joins and caching.
