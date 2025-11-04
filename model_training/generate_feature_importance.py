#!/usr/bin/env python3
"""
Generate feature importance report for CatBoost (Native categorical) and RandomForest.
Outputs:
  - docs/FEATURE_IMPORTANCE.md
"""
import os
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from tabulate import tabulate

try:
    from catboost import CatBoostClassifier
except Exception as e:
    CatBoostClassifier = None  # type: ignore
    print(f"[WARN] CatBoost unavailable: {e}")

from model_bakeoff import calculate_sample_weights, prepare_data

def train_catboost_native(df: pd.DataFrame):
    if CatBoostClassifier is None:
        return None, None
    df = prepare_data(df)
    features = ['home_team','away_team','is_neutral','home_rank','away_rank']
    target = 'home_win'
    # CatBoost native
    model = CatBoostClassifier(random_state=42, verbose=0, cat_features=['home_team','away_team'])
    weights = calculate_sample_weights(df)
    model.fit(df[features], df[target], sample_weight=weights)
    importances = model.get_feature_importance()
    return model, list(zip(features, importances))

def train_random_forest(df: pd.DataFrame):
    df = prepare_data(df)
    all_teams = pd.concat([df['home_team'], df['away_team']]).unique()
    enc = LabelEncoder().fit(all_teams)
    df['home_team_encoded'] = df['home_team'].map({t:i for i,t in enumerate(enc.classes_)})
    df['away_team_encoded'] = df['away_team'].map({t:i for i,t in enumerate(enc.classes_)})
    features = ['home_team_encoded','away_team_encoded','is_neutral','home_rank','away_rank']
    target = 'home_win'
    rf = RandomForestClassifier(n_estimators=200, max_depth=25, min_samples_split=5, random_state=42, n_jobs=-1)
    weights = calculate_sample_weights(df)
    rf.fit(df[features], df[target], sample_weight=weights)
    return rf, list(zip(features, rf.feature_importances_))

def main():
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    path = os.path.join(data_dir, 'Completed_Games.csv')
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    df = pd.read_csv(path)
    cat_model, cat_importances = train_catboost_native(df)
    rf_model, rf_importances = train_random_forest(df)

    docs_dir = os.path.join(os.path.dirname(__file__), '..', 'docs')
    os.makedirs(docs_dir, exist_ok=True)
    md_path = os.path.join(docs_dir, 'FEATURE_IMPORTANCE.md')
    with open(md_path, 'w') as f:
        f.write('# Feature Importance Report\n\n')
        if cat_importances:
            f.write('## CatBoost (Native)\n\n')
            cat_df = pd.DataFrame(cat_importances, columns=['feature','importance']).sort_values('importance', ascending=False)
            f.write(tabulate(cat_df.values, headers=list(cat_df.columns), tablefmt='pipe', floatfmt='.4f'))
            f.write('\n\n')
        else:
            f.write('CatBoost not available.\n\n')
        f.write('## RandomForest\n\n')
        rf_df = pd.DataFrame(rf_importances, columns=['feature','importance']).sort_values('importance', ascending=False)
        f.write(tabulate(rf_df.values, headers=list(rf_df.columns), tablefmt='pipe', floatfmt='.4f'))
        f.write('\n')
    print(f"[INFO] Wrote {md_path}")

if __name__ == '__main__':
    main()
