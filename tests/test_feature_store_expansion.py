import pandas as pd
from model_training.feature_store import build_feature_store


def test_feature_store_expanded_columns():
    # Minimal synthetic games to produce feature rows
    data = [
        {'game_id':f'g{i}','home_team':f'H{i%2}','away_team':f'A{i%3}','home_score':70+i,'away_score':65+i,'season':'2024-25','date':f'2024-11-{i:02d}'}
        for i in range(1,8)
    ]
    df = pd.DataFrame(data)
    fs = build_feature_store(df)
    expected_cols = {
        'win_pct_last5_vs10','point_diff_last5_vs10','recent_strength_index_5'
    }
    assert expected_cols.issubset(set(fs.columns))
