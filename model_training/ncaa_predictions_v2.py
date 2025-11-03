"""
NCAA Basketball Game Prediction Model - Enhanced Multi-Season Version
This script uses scikit-learn to predict the outcomes of upcoming NCAA basketball games
based on multiple seasons of historical data with advanced features.

Improvements:
- Multi-season training data (2020-21 through 2024-25)
- Rolling window statistics (last 5/10 games)
- Team embeddings and historical features
- Time-weighted training (recent games weighted higher)
- Enhanced hyperparameter search
"""

import sys
import datetime
import warnings
import os
import gc

# Suppress multiprocessing resource tracker warnings in Python 3.13+
warnings.filterwarnings('ignore', category=UserWarning, module='multiprocessing')
os.environ['PYTHONWARNINGS'] = 'ignore::UserWarning'

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split, cross_val_score, RandomizedSearchCV
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, log_loss, roc_auc_score
from sklearn.impute import SimpleImputer
from scipy.stats import randint, uniform


def load_data():
    """Load completed and upcoming games from CSV files."""
    print("="*80)
    print("LOADING DATA")
    print("="*80)
    
    # Determine data directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(os.path.dirname(script_dir), 'data')
    
    completed_path = os.path.join(data_dir, 'Completed_Games.csv')
    upcoming_path = os.path.join(data_dir, 'Upcoming_Games.csv')
    
    completed_games = pd.read_csv(completed_path)
    upcoming_games = pd.read_csv(upcoming_path)
    
    print(f"Loaded {len(completed_games):,} completed games and {len(upcoming_games)} upcoming games")
    
    # Show season breakdown if available
    if 'season' in completed_games.columns:
        print(f"\nCompleted games by season:")
        season_counts = completed_games['season'].value_counts().sort_index()
        for season, count in season_counts.items():
            print(f"  {season}: {count:,} games")
    
    # Check if there are any upcoming games
    if upcoming_games.empty:
        print("\nNo upcoming games found. Will only train model.")
    
    return completed_games, upcoming_games


def extract_win_pct(record):
    """Convert records (e.g., '10-5') to win percentage."""
    if pd.isna(record) or record == '':
        return np.nan
    try:
        wins, losses = record.split('-')
        wins, losses = int(wins), int(losses)
        if wins + losses > 0:
            return wins / (wins + losses)
        return 0.5
    except:
        return np.nan


def process_rank(rank):
    """Process team rankings, using 50 for unranked teams."""
    if pd.isna(rank):
        return 50
    try:
        return float(rank)
    except:
        return 50


def calculate_rolling_stats(completed_games, windows=[5, 10]):
    """Calculate rolling window statistics for each team.
    
    CRITICAL: Uses LAGGED statistics to prevent data leakage.
    For each game, we calculate stats based ONLY on games that occurred BEFORE it.
    """
    print("\n" + "="*80)
    print("CALCULATING ROLLING WINDOW STATISTICS (LAGGED)")
    print("="*80)
    print(f"Windows: Last {windows[0]} games, Last {windows[1]} games")
    print("Using lagged calculations to prevent look-ahead bias")
    
    # Sort by date for proper rolling calculations
    completed_games = completed_games.copy()
    completed_games['game_day'] = pd.to_datetime(completed_games['game_day'])
    completed_games = completed_games.sort_values('game_day')
    
    # Create a list to store team game records chronologically
    team_games = []
    
    # Process home games
    for _, row in completed_games.iterrows():
        team_games.append({
            'team': row['home_team'],
            'game_id': row['game_id'],
            'game_day': row['game_day'],
            'season': row.get('season', ''),
            'points': row['home_score'],
            'opp_points': row['away_score'],
            'won': 1 if row['home_score'] > row['away_score'] else 0,
            'is_home': 1
        })
    
    # Process away games
    for _, row in completed_games.iterrows():
        team_games.append({
            'team': row['away_team'],
            'game_id': row['game_id'],
            'game_day': row['game_day'],
            'season': row.get('season', ''),
            'points': row['away_score'],
            'opp_points': row['home_score'],
            'won': 1 if row['away_score'] > row['home_score'] else 0,
            'is_home': 0
        })
    
    # Convert to DataFrame and sort
    team_games_df = pd.DataFrame(team_games)
    team_games_df = team_games_df.sort_values(['team', 'game_day'])
    
    # Calculate rolling statistics
    rolling_stats = {}
    
    for team in team_games_df['team'].unique():
        team_data = team_games_df[team_games_df['team'] == team].copy()
        team_data = team_data.reset_index(drop=True)
        
        # CRITICAL FIX: Use .shift() to lag the rolling statistics
        # This ensures we only use games BEFORE the current one
        for window in windows:
            # Shift by 1 to exclude current game from rolling window
            team_data[f'last_{window}_ppg'] = team_data['points'].rolling(window, min_periods=1).mean().shift(1)
            team_data[f'last_{window}_oppg'] = team_data['opp_points'].rolling(window, min_periods=1).mean().shift(1)
            team_data[f'last_{window}_win_pct'] = team_data['won'].rolling(window, min_periods=1).mean().shift(1)
        
        # Calculate win streaks (also lagged)
        # Group by consecutive wins/losses and count, then shift
        win_streak_series = team_data['won'].groupby((team_data['won'] != team_data['won'].shift()).cumsum()).cumsum()
        loss_streak_series = (1 - team_data['won']).groupby(((1 - team_data['won']) != (1 - team_data['won']).shift()).cumsum()).cumsum()
        
        # Shift to exclude current game
        team_data['win_streak'] = win_streak_series.shift(1, fill_value=0)
        team_data['loss_streak'] = loss_streak_series.shift(1, fill_value=0)
        
        # Fill NaN values in first game with defaults
        for window in windows:
            team_data[f'last_{window}_ppg'].fillna(70, inplace=True)  # NCAA average
            team_data[f'last_{window}_oppg'].fillna(70, inplace=True)
            team_data[f'last_{window}_win_pct'].fillna(0.5, inplace=True)
        
        # Store in dictionary by game_id
        for _, row in team_data.iterrows():
            game_id = row['game_id']
            if game_id not in rolling_stats:
                rolling_stats[game_id] = {}
            
            team_key = team
            rolling_stats[game_id][team_key] = {
                f'last_{window}_ppg': row[f'last_{window}_ppg'] for window in windows
            }
            rolling_stats[game_id][team_key].update({
                f'last_{window}_oppg': row[f'last_{window}_oppg'] for window in windows
            })
            rolling_stats[game_id][team_key].update({
                f'last_{window}_win_pct': row[f'last_{window}_win_pct'] for window in windows
            })
            rolling_stats[game_id][team_key]['win_streak'] = row['win_streak']
            rolling_stats[game_id][team_key]['loss_streak'] = row['loss_streak']
    
    print(f"✓ Calculated lagged rolling statistics for {len(rolling_stats):,} games")
    return rolling_stats


def add_rolling_features(df, rolling_stats, windows=[5, 10]):
    """Add rolling window features to games dataframe."""
    # Initialize columns
    for window in windows:
        df[f'home_last_{window}_ppg'] = np.nan
        df[f'home_last_{window}_oppg'] = np.nan
        df[f'home_last_{window}_win_pct'] = np.nan
        df[f'away_last_{window}_ppg'] = np.nan
        df[f'away_last_{window}_oppg'] = np.nan
        df[f'away_last_{window}_win_pct'] = np.nan
    
    df['home_win_streak'] = 0
    df['home_loss_streak'] = 0
    df['away_win_streak'] = 0
    df['away_loss_streak'] = 0
    
    # Populate from rolling_stats dictionary
    for i, row in df.iterrows():
        game_id = row['game_id']
        home_team = row['home_team']
        away_team = row['away_team']
        
        if game_id in rolling_stats:
            if home_team in rolling_stats[game_id]:
                home_stats = rolling_stats[game_id][home_team]
                for window in windows:
                    df.at[i, f'home_last_{window}_ppg'] = home_stats.get(f'last_{window}_ppg', np.nan)
                    df.at[i, f'home_last_{window}_oppg'] = home_stats.get(f'last_{window}_oppg', np.nan)
                    df.at[i, f'home_last_{window}_win_pct'] = home_stats.get(f'last_{window}_win_pct', np.nan)
                df.at[i, 'home_win_streak'] = home_stats.get('win_streak', 0)
                df.at[i, 'home_loss_streak'] = home_stats.get('loss_streak', 0)
            
            if away_team in rolling_stats[game_id]:
                away_stats = rolling_stats[game_id][away_team]
                for window in windows:
                    df.at[i, f'away_last_{window}_ppg'] = away_stats.get(f'last_{window}_ppg', np.nan)
                    df.at[i, f'away_last_{window}_oppg'] = away_stats.get(f'last_{window}_oppg', np.nan)
                    df.at[i, f'away_last_{window}_win_pct'] = away_stats.get(f'last_{window}_win_pct', np.nan)
                df.at[i, 'away_win_streak'] = away_stats.get('win_streak', 0)
                df.at[i, 'away_loss_streak'] = away_stats.get('loss_streak', 0)
    
    return df


def calculate_team_historical_stats(completed_games):
    """Calculate overall team statistics across all seasons."""
    print("\n" + "="*80)
    print("CALCULATING TEAM HISTORICAL STATISTICS")
    print("="*80)
    
    team_stats = {}
    
    for _, row in completed_games.iterrows():
        home_team = row['home_team']
        away_team = row['away_team']
        
        # Initialize if not exists
        if home_team not in team_stats:
            team_stats[home_team] = {'games': 0, 'points_scored': 0, 'points_allowed': 0, 'wins': 0}
        if away_team not in team_stats:
            team_stats[away_team] = {'games': 0, 'points_scored': 0, 'points_allowed': 0, 'wins': 0}
        
        # Update stats
        team_stats[home_team]['games'] += 1
        team_stats[home_team]['points_scored'] += row['home_score']
        team_stats[home_team]['points_allowed'] += row['away_score']
        team_stats[home_team]['wins'] += 1 if row['home_score'] > row['away_score'] else 0
        
        team_stats[away_team]['games'] += 1
        team_stats[away_team]['points_scored'] += row['away_score']
        team_stats[away_team]['points_allowed'] += row['home_score']
        team_stats[away_team]['wins'] += 1 if row['away_score'] > row['home_score'] else 0
    
    # Calculate averages
    for team in team_stats:
        if team_stats[team]['games'] > 0:
            team_stats[team]['avg_points_scored'] = team_stats[team]['points_scored'] / team_stats[team]['games']
            team_stats[team]['avg_points_allowed'] = team_stats[team]['points_allowed'] / team_stats[team]['games']
            team_stats[team]['win_pct'] = team_stats[team]['wins'] / team_stats[team]['games']
            team_stats[team]['point_diff'] = team_stats[team]['avg_points_scored'] - team_stats[team]['avg_points_allowed']
        else:
            team_stats[team]['avg_points_scored'] = 70
            team_stats[team]['avg_points_allowed'] = 70
            team_stats[team]['win_pct'] = 0.5
            team_stats[team]['point_diff'] = 0
    
    print(f"✓ Calculated statistics for {len(team_stats)} teams")
    print(f"  Average games per team: {np.mean([s['games'] for s in team_stats.values()]):.1f}")
    
    return team_stats


def add_team_encodings_and_features(df, team_stats):
    """Add team ID encodings and historical features."""
    print("\n" + "="*80)
    print("ADDING TEAM EMBEDDINGS AND HISTORICAL FEATURES")
    print("="*80)
    
    # Create label encoder for teams
    all_teams = list(set(df['home_team'].unique()) | set(df['away_team'].unique()))
    label_encoder = LabelEncoder()
    label_encoder.fit(all_teams)
    
    # Add team ID encodings
    df['home_team_id'] = label_encoder.transform(df['home_team'])
    df['away_team_id'] = label_encoder.transform(df['away_team'])
    
    print(f"✓ Encoded {len(all_teams)} unique teams")
    
    # Add historical statistics
    df['home_hist_ppg'] = df['home_team'].map(lambda x: team_stats.get(x, {}).get('avg_points_scored', 70))
    df['home_hist_oppg'] = df['home_team'].map(lambda x: team_stats.get(x, {}).get('avg_points_allowed', 70))
    df['home_hist_win_pct'] = df['home_team'].map(lambda x: team_stats.get(x, {}).get('win_pct', 0.5))
    df['home_hist_point_diff'] = df['home_team'].map(lambda x: team_stats.get(x, {}).get('point_diff', 0))
    
    df['away_hist_ppg'] = df['away_team'].map(lambda x: team_stats.get(x, {}).get('avg_points_scored', 70))
    df['away_hist_oppg'] = df['away_team'].map(lambda x: team_stats.get(x, {}).get('avg_points_allowed', 70))
    df['away_hist_win_pct'] = df['away_team'].map(lambda x: team_stats.get(x, {}).get('win_pct', 0.5))
    df['away_hist_point_diff'] = df['away_team'].map(lambda x: team_stats.get(x, {}).get('point_diff', 0))
    
    print(f"✓ Added team embeddings and historical features")
    
    return df, label_encoder


def calculate_time_weights(df):
    """Calculate sample weights based on season recency."""
    print("\n" + "="*80)
    print("CALCULATING TIME-WEIGHTED SAMPLE WEIGHTS")
    print("="*80)
    
    if 'season' not in df.columns:
        print("No season column found, using uniform weights")
        return np.ones(len(df))
    
    # Define weights by season (more recent = higher weight)
    season_weights = {
        '2024-25': 1.0,
        '2023-24': 0.9,
        '2022-23': 0.8,
        '2021-22': 0.7,
        '2020-21': 0.6
    }
    
    weights = df['season'].map(lambda x: season_weights.get(x, 0.5))
    
    print("Season weight distribution:")
    for season, weight in sorted(season_weights.items(), reverse=True):
        count = len(df[df['season'] == season])
        if count > 0:
            print(f"  {season}: weight={weight:.1f}, games={count:,}")
    
    return weights.values


def preprocess_data(completed_games, upcoming_games):
    """Clean and preprocess the game data with enhanced features."""
    print("\n" + "="*80)
    print("DATA PREPROCESSING")
    print("="*80)
    
    # Convert records to win percentage
    completed_games['home_win_pct'] = completed_games['home_record'].apply(extract_win_pct)
    completed_games['away_win_pct'] = completed_games['away_record'].apply(extract_win_pct)
    upcoming_games['home_win_pct'] = upcoming_games['home_record'].apply(extract_win_pct)
    upcoming_games['away_win_pct'] = upcoming_games['away_record'].apply(extract_win_pct)
    
    # Handle ranks
    completed_games['home_rank_processed'] = completed_games['home_rank'].apply(process_rank)
    completed_games['away_rank_processed'] = completed_games['away_rank'].apply(process_rank)
    upcoming_games['home_rank_processed'] = upcoming_games['home_rank'].apply(process_rank)
    upcoming_games['away_rank_processed'] = upcoming_games['away_rank'].apply(process_rank)
    
    # Create target variable: did home team win?
    completed_games['home_team_won'] = (completed_games['home_score'] > completed_games['away_score']).astype(int)
    
    # Calculate rolling statistics
    rolling_stats = calculate_rolling_stats(completed_games)
    completed_games = add_rolling_features(completed_games, rolling_stats)
    upcoming_games = add_rolling_features(upcoming_games, rolling_stats)
    
    # Calculate team historical stats
    team_stats = calculate_team_historical_stats(completed_games)
    
    # Add team encodings and features
    completed_games, label_encoder = add_team_encodings_and_features(completed_games, team_stats)
    upcoming_games, _ = add_team_encodings_and_features(upcoming_games, team_stats)
    
    print("\n✓ Preprocessing completed successfully!")
    
    return completed_games, upcoming_games, team_stats, label_encoder


def create_model_features(df):
    """Create derived features for modeling."""
    # Rank difference
    df['rank_difference'] = df['away_rank_processed'] - df['home_rank_processed']
    
    # Historical differences
    df['hist_win_pct_diff'] = df['home_hist_win_pct'] - df['away_hist_win_pct']
    df['hist_ppg_diff'] = df['home_hist_ppg'] - df['away_hist_ppg']
    df['hist_oppg_diff'] = df['away_hist_oppg'] - df['home_hist_oppg']  # Lower is better for defense
    df['hist_point_diff_advantage'] = df['home_hist_point_diff'] - df['away_hist_point_diff']
    
    # Recent form differences (last 5 games)
    if 'home_last_5_ppg' in df.columns:
        df['recent_ppg_diff'] = df['home_last_5_ppg'] - df['away_last_5_ppg']
        df['recent_oppg_diff'] = df['away_last_5_oppg'] - df['home_last_5_oppg']
        df['recent_form_diff'] = df['home_last_5_win_pct'] - df['away_last_5_win_pct']
    
    # Momentum indicators
    if 'home_win_streak' in df.columns:
        df['momentum_diff'] = df['home_win_streak'] - df['away_win_streak']
    
    # Home court advantage
    df['home_advantage'] = (~df['is_neutral'].astype(bool)).astype(int)
    
    return df


def build_and_train_model(completed_games):
    """Build and train the prediction model with enhanced features."""
    print("\n" + "="*80)
    print("MODEL BUILDING AND TRAINING")
    print("="*80)
    
    # Add derived features
    completed_games = create_model_features(completed_games)
    
    # Select features for modeling
    features = [
        # Team identity
        'home_team_id', 'away_team_id',
        
        # Rankings
        'home_rank_processed', 'away_rank_processed', 'rank_difference',
        
        # Historical performance
        'home_hist_win_pct', 'away_hist_win_pct', 'hist_win_pct_diff',
        'home_hist_ppg', 'away_hist_ppg', 'hist_ppg_diff',
        'home_hist_oppg', 'away_hist_oppg', 'hist_oppg_diff',
        'hist_point_diff_advantage',
        
        # Recent form (last 5 games)
        'home_last_5_ppg', 'away_last_5_ppg', 'recent_ppg_diff',
        'home_last_5_oppg', 'away_last_5_oppg', 'recent_oppg_diff',
        'home_last_5_win_pct', 'away_last_5_win_pct', 'recent_form_diff',
        
        # Last 10 games
        'home_last_10_win_pct', 'away_last_10_win_pct',
        
        # Momentum
        'home_win_streak', 'away_win_streak', 'momentum_diff',
        
        # Context
        'home_advantage'
    ]
    
    # Filter features that exist in the dataframe
    available_features = [f for f in features if f in completed_games.columns]
    print(f"\nUsing {len(available_features)} features:")
    for f in available_features:
        print(f"  - {f}")
    
    # Filter rows with complete data
    model_data = completed_games.dropna(subset=available_features)
    print(f"\nUsing {len(model_data):,} out of {len(completed_games):,} games for modeling")
    
    X = model_data[available_features]
    y = model_data['home_team_won']
    
    # Calculate sample weights
    sample_weights = calculate_time_weights(model_data)
    
    # Split data
    X_train, X_test, y_train, y_test, weights_train, weights_test = train_test_split(
        X, y, sample_weights, test_size=0.25, random_state=42
    )
    
    print(f"\nTraining set: {len(X_train):,} games")
    print(f"Test set: {len(X_test):,} games")
    
    # Create preprocessing pipeline
    numeric_transformer = Pipeline(steps=[
        ('imputer', SimpleImputer(strategy='median')),
        ('scaler', StandardScaler())
    ])
    
    # Create full pipeline
    model_pipeline = Pipeline(steps=[
        ('preprocessor', numeric_transformer),
        ('classifier', RandomForestClassifier(random_state=42))
    ])
    
    # Enhanced hyperparameter search
    print("\n" + "="*80)
    print("HYPERPARAMETER OPTIMIZATION")
    print("="*80)
    print("Using RandomizedSearchCV with 50 iterations...")
    
    param_distributions = {
        'classifier__n_estimators': randint(100, 500),
        'classifier__max_depth': [None] + list(randint(10, 50).rvs(10)),
        'classifier__min_samples_split': randint(2, 20),
        'classifier__min_samples_leaf': randint(1, 10),
        'classifier__max_features': ['sqrt', 'log2', None],
        'classifier__bootstrap': [True, False]
    }
    
    # Set environment for multiprocessing
    cpu_count = os.cpu_count()
    if cpu_count:
        os.environ['LOKY_MAX_CPU_COUNT'] = str(max(1, cpu_count - 1))
    
    random_search = RandomizedSearchCV(
        model_pipeline,
        param_distributions,
        n_iter=50,
        cv=5,
        n_jobs=-1,
        verbose=0,
        random_state=42,
        scoring='accuracy'
    )
    
    random_search.fit(X_train, y_train, classifier__sample_weight=weights_train)
    
    print(f"\n✓ Best parameters found:")
    for param, value in random_search.best_params_.items():
        print(f"  {param}: {value}")
    
    best_model = random_search.best_estimator_
    
    # Evaluate on test data
    print("\n" + "="*80)
    print("MODEL EVALUATION")
    print("="*80)
    
    y_pred = best_model.predict(X_test)
    y_pred_proba = best_model.predict_proba(X_test)
    
    accuracy = accuracy_score(y_test, y_pred, sample_weight=weights_test)
    log_loss_score = log_loss(y_test, y_pred_proba, sample_weight=weights_test)
    roc_auc = roc_auc_score(y_test, y_pred_proba[:, 1], sample_weight=weights_test)
    
    print(f"Model accuracy on test data: {accuracy:.4f}")
    print(f"Log loss: {log_loss_score:.4f}")
    print(f"ROC-AUC score: {roc_auc:.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, sample_weight=weights_test))
    
    # Cross-validation
    print("\nPerforming 5-fold cross-validation...")
    cv_scores = cross_val_score(best_model, X, y, cv=5, scoring='accuracy')
    print(f"Cross-validation accuracy: {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")
    
    # Feature importance
    feature_importance = best_model.named_steps['classifier'].feature_importances_
    sorted_idx = np.argsort(feature_importance)[::-1]
    
    print("\nTop 10 Most Important Features:")
    for i in range(min(10, len(available_features))):
        idx = sorted_idx[i]
        print(f"  {i+1}. {available_features[idx]}: {feature_importance[idx]:.4f}")
    
    # Plot feature importance
    plt.figure(figsize=(12, 10))
    top_n = min(20, len(available_features))
    top_idx = sorted_idx[:top_n]
    plt.barh(range(top_n), feature_importance[top_idx])
    plt.yticks(range(top_n), [available_features[i] for i in top_idx])
    plt.xlabel('Importance')
    plt.title(f'Top {top_n} Feature Importance')
    plt.tight_layout()
    
    # Save to data/ directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(os.path.dirname(script_dir), 'data')
    plot_path = os.path.join(data_dir, 'feature_importance.png')
    plt.savefig(plot_path, dpi=100, bbox_inches='tight')
    print(f"\n✓ Feature importance plot saved to '{plot_path}'")
    plt.close()
    
    return best_model, available_features


def make_predictions(best_model, features, upcoming_games):
    """Make predictions on upcoming games."""
    print("\n" + "="*80)
    print("PREDICTING UPCOMING GAMES")
    print("="*80)
    
    if upcoming_games.empty:
        print("No upcoming games to predict.")
        return pd.DataFrame()
    
    # Add derived features
    upcoming_games = create_model_features(upcoming_games)
    
    # Prepare data
    existing_features = [f for f in features if f in upcoming_games.columns]
    upcoming_features = upcoming_games.dropna(subset=existing_features)
    
    if upcoming_features.empty:
        print("No upcoming games with sufficient data for prediction.")
        return pd.DataFrame()
    
    X_upcoming = upcoming_features[existing_features]
    
    # Make predictions
    predictions = best_model.predict(X_upcoming)
    prediction_probabilities = best_model.predict_proba(X_upcoming)
    
    # Add predictions to dataframe
    upcoming_features = upcoming_features.copy()
    upcoming_features['predicted_winner'] = predictions
    upcoming_features['home_win_probability'] = prediction_probabilities[:, 1]
    upcoming_features['away_win_probability'] = prediction_probabilities[:, 0]
    upcoming_features['confidence'] = prediction_probabilities.max(axis=1)
    
    # Determine predicted winner name
    upcoming_features['predicted_winner_name'] = upcoming_features.apply(
        lambda row: row['home_team'] if row['predicted_winner'] == 1 else row['away_team'],
        axis=1
    )
    
    print(f"\n✓ Generated predictions for {len(upcoming_features)} upcoming games")
    
    return upcoming_features


def export_results_and_update_readme(predictions):
    """Export predictions to CSV and update README."""
    if predictions.empty:
        print("\nNo predictions to export.")
        return
    
    # Select columns for export
    export_columns = [
        'game_day', 'home_team', 'away_team',
        'predicted_winner_name', 'home_win_probability', 'away_win_probability', 'confidence'
    ]
    
    available_export_cols = [col for col in export_columns if col in predictions.columns]
    predictions_export = predictions[available_export_cols].copy()
    
    # Sort by confidence
    predictions_export = predictions_export.sort_values('confidence', ascending=False)
    
    # Export to CSV in data/ directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(os.path.dirname(script_dir), 'data')
    predictions_path = os.path.join(data_dir, 'NCAA_Game_Predictions.csv')
    
    predictions_export.to_csv(predictions_path, index=False)
    print(f"\n✓ Exported predictions to '{predictions_path}'")
    
    # Update README with high-confidence predictions
    high_confidence = predictions_export[predictions_export['confidence'] >= 0.75]
    
    readme_content = f"""# NCAA Basketball Predictions

## Latest Predictions
*Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*

### High Confidence Predictions (≥75%)
Total games analyzed: {len(predictions_export)}
High confidence predictions: {len(high_confidence)}

"""
    
    if not high_confidence.empty:
        readme_content += "| Date | Matchup | Predicted Winner | Confidence |\n"
        readme_content += "|------|---------|-----------------|------------|\n"
        
        for _, row in high_confidence.head(20).iterrows():
            matchup = f"{row['home_team']} vs {row['away_team']}"
            confidence_pct = f"{row['confidence']*100:.1f}%"
            readme_content += f"| {row['game_day']} | {matchup} | **{row['predicted_winner_name']}** | {confidence_pct} |\n"
    else:
        readme_content += "*No high-confidence predictions available.*\n"
    
    readme_content += f"\n### Model Performance\n"
    readme_content += f"- Training on multi-season data (2020-21 through 2024-25)\n"
    readme_content += f"- Features include: team rankings, historical stats, recent form, momentum\n"
    readme_content += f"- Enhanced with rolling window statistics and team embeddings\n"
    
    # Read existing README to preserve other sections
    try:
        with open('README.md', 'r') as f:
            existing_readme = f.read()
        
        # Find where to insert predictions
        if '## Latest Predictions' in existing_readme:
            # Replace existing predictions section
            start = existing_readme.find('## Latest Predictions')
            end = existing_readme.find('##', start + 1)
            if end == -1:
                end = len(existing_readme)
            new_readme = existing_readme[:start] + readme_content + '\n' + existing_readme[end:]
        else:
            # Append to end
            new_readme = existing_readme + '\n\n' + readme_content
        
        with open('README.md', 'w') as f:
            f.write(new_readme)
        
        print("✓ Updated README.md with predictions")
    except Exception as e:
        print(f"Note: Could not update README.md: {e}")


def main():
    """Main function to orchestrate the prediction workflow."""
    print("\n" + "="*80)
    print("NCAA BASKETBALL PREDICTION MODEL")
    print("Enhanced Multi-Season Version with Advanced Features")
    print("="*80)
    
    try:
        # Load data
        completed_games, upcoming_games = load_data()
        
        # Preprocess data
        completed_games, upcoming_games, team_stats, label_encoder = preprocess_data(
            completed_games, upcoming_games
        )
        
        # Build and train model
        best_model, features = build_and_train_model(completed_games)
        
        # Make predictions
        predictions = make_predictions(best_model, features, upcoming_games)
        
        # Export results
        export_results_and_update_readme(predictions)
        
        print("\n" + "="*80)
        print("PREDICTION WORKFLOW COMPLETED SUCCESSFULLY!")
        print("="*80)
        
    except Exception as e:
        print(f"\n❌ Error in prediction workflow: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Cleanup
        plt.close('all')
        gc.collect()


if __name__ == "__main__":
    # Redirect stderr after main() to suppress any remaining cleanup messages
    try:
        main()
    finally:
        sys.stderr = open(os.devnull, 'w')

