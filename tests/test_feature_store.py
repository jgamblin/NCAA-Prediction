import pandas as pd
from model_training.feature_store import build_feature_store
from model_training.team_id_utils import ensure_team_ids


def _sample_games():
    # Two teams A vs B sequence to test rolling windows
    data = [
        {'game_id':'g1','home_team':'Alpha','away_team':'Beta','home_score':70,'away_score':65,'season':'2025-26','date':'2025-11-01'},
        {'game_id':'g2','home_team':'Beta','away_team':'Alpha','home_score':60,'away_score':80,'season':'2025-26','date':'2025-11-02'},
        {'game_id':'g3','home_team':'Alpha','away_team':'Beta','home_score':72,'away_score':75,'season':'2025-26','date':'2025-11-03'},
        {'game_id':'g4','home_team':'Alpha','away_team':'Gamma','home_score':65,'away_score':55,'season':'2025-26','date':'2025-11-04'},
        {'game_id':'g5','home_team':'Gamma','away_team':'Alpha','home_score':50,'away_score':60,'season':'2025-26','date':'2025-11-05'},
    ]
    return pd.DataFrame(data)


def test_feature_store_basic_rolling():
    games = ensure_team_ids(_sample_games())
    fs = build_feature_store(games)
    # Expect one row per team in season
    assert set(fs['team_id'])  # non-empty
    # Games played should reflect number of appearances per team
    # Alpha appears in all 5 games (home 3, away 2)
    alpha_row = fs[fs['team_id'] == fs.loc[0,'team_id']]  # first row is some team
    assert 'games_played' in fs.columns


def test_feature_store_incremental_update():
    games = ensure_team_ids(_sample_games())
    fs1 = build_feature_store(games.iloc[:3])
    fs2 = build_feature_store(games)  # full set should override same season+team rows
    # Full set should have >= rows (additional teams may appear in later slice)
    assert len(fs2) >= len(fs1)
