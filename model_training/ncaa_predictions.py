"""
NCAA Basketball Game Prediction Model
This script uses scikit-learn to predict the outcomes of upcoming NCAA basketball games
based on completed games data.
"""

import sys
import datetime
import warnings
import os

# Suppress multiprocessing resource tracker warnings in Python 3.13+
# These are harmless cleanup warnings that don't affect functionality
warnings.filterwarnings('ignore', category=UserWarning, module='multiprocessing')
os.environ['PYTHONWARNINGS'] = 'ignore::UserWarning'

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for headless environments
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.impute import SimpleImputer


def load_data():
    """Load completed and upcoming games from CSV files."""
    print("Loading data...")
    completed_games = pd.read_csv('Completed_Games.csv')
    upcoming_games = pd.read_csv('Upcoming_Games.csv')
    
    print(f"Loaded {len(completed_games)} completed games and {len(upcoming_games)} upcoming games")
    
    # Check if there are any upcoming games
    if upcoming_games.empty:
        print("No upcoming games found. Exiting.")
        sys.exit(0)
    
    return completed_games, upcoming_games


def explore_data(completed_games, upcoming_games):
    """Print basic data exploration information."""
    print("\n" + "="*50)
    print("DATA EXPLORATION")
    print("="*50)
    print("\nCompleted games columns:")
    print(completed_games.columns.tolist())
    print("\nMissing values in completed games:")
    missing = completed_games.isna().sum()[completed_games.isna().sum() > 0]
    if len(missing) > 0:
        print(missing)
    else:
        print("No missing values")
    print("\nUpcoming games columns:")
    print(upcoming_games.columns.tolist())


def extract_win_pct(record):
    """Convert records (e.g., '10-5') to win percentage."""
    if pd.isna(record) or record == '':
        return np.nan
    try:
        wins, losses = record.split('-')
        wins, losses = int(wins), int(losses)
        if wins + losses > 0:
            return wins / (wins + losses)
        return 0.5  # Default for teams with no games
    except:
        return np.nan


def process_rank(rank):
    """Process team rankings, using 50 for unranked teams."""
    if pd.isna(rank):
        return 50  # Default value for unranked teams
    try:
        return float(rank)
    except:
        return 50


def preprocess_data(completed_games, upcoming_games):
    """Clean and preprocess the game data."""
    print("\n" + "="*50)
    print("DATA PREPROCESSING")
    print("="*50)
    
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
    
    # Create point spread feature
    completed_games['point_spread'] = pd.to_numeric(completed_games['home_point_spread'], errors='coerce')
    
    # Create target variable: did home team win?
    completed_games['home_team_won'] = (completed_games['home_score'] > completed_games['away_score']).astype(int)
    
    return completed_games, upcoming_games


def calculate_team_stats(completed_games):
    """Calculate team statistics based on completed games."""
    print("Calculating team statistics...")
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
        else:
            team_stats[team]['avg_points_scored'] = 70  # Default values
            team_stats[team]['avg_points_allowed'] = 70
            team_stats[team]['win_pct'] = 0.5
    
    return team_stats


def add_team_stats(df, team_stats):
    """Add team statistics to games dataframe."""
    # Initialize new columns
    df['home_avg_points'] = np.nan
    df['home_avg_points_allowed'] = np.nan
    df['home_calculated_win_pct'] = np.nan
    df['away_avg_points'] = np.nan
    df['away_avg_points_allowed'] = np.nan
    df['away_calculated_win_pct'] = np.nan
    
    # Populate with stats
    for i, row in df.iterrows():
        home_team = row['home_team']
        away_team = row['away_team']
        
        if home_team in team_stats:
            df.at[i, 'home_avg_points'] = team_stats[home_team]['avg_points_scored']
            df.at[i, 'home_avg_points_allowed'] = team_stats[home_team]['avg_points_allowed']
            df.at[i, 'home_calculated_win_pct'] = team_stats[home_team]['win_pct']
        
        if away_team in team_stats:
            df.at[i, 'away_avg_points'] = team_stats[away_team]['avg_points_scored']
            df.at[i, 'away_avg_points_allowed'] = team_stats[away_team]['avg_points_allowed']
            df.at[i, 'away_calculated_win_pct'] = team_stats[away_team]['win_pct']
    
    return df


def create_model_features(df):
    """Create additional features for modeling."""
    df['rank_difference'] = df['away_rank_processed'] - df['home_rank_processed']
    df['win_pct_difference'] = df['home_calculated_win_pct'] - df['away_calculated_win_pct']
    df['scoring_diff'] = df['home_avg_points'] - df['away_avg_points']
    df['defense_diff'] = df['away_avg_points_allowed'] - df['home_avg_points_allowed']
    df['points_diff'] = df['home_avg_points'] - df['away_avg_points']
    df['allowed_points_diff'] = df['home_avg_points_allowed'] - df['away_avg_points_allowed']
    
    # Home court advantage (is_neutral=False means home advantage exists)
    df['home_advantage'] = (~df['is_neutral'].astype(bool)).astype(int)
    
    return df


def build_and_train_model(completed_games):
    """Build and train the prediction model."""
    print("\n" + "="*50)
    print("MODEL BUILDING")
    print("="*50)
    
    # Select features for modeling
    features = [
        'home_rank_processed', 'away_rank_processed', 'rank_difference',
        'home_calculated_win_pct', 'away_calculated_win_pct', 'win_pct_difference',
        'home_avg_points', 'away_avg_points', 'scoring_diff',
        'home_avg_points_allowed', 'away_avg_points_allowed', 'defense_diff',
        'home_advantage', 'points_diff', 'allowed_points_diff'
    ]
    
    # Filter rows with complete data for features
    model_data = completed_games.dropna(subset=features)
    print(f"Using {len(model_data)} out of {len(completed_games)} games for modeling")
    
    X = model_data[features]
    y = model_data['home_team_won']
    
    # Split data into training and testing sets
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42)
    
    # Create preprocessing pipeline
    numeric_transformer = Pipeline(steps=[
        ('imputer', SimpleImputer(strategy='median')),
        ('scaler', StandardScaler())
    ])
    
    # Create full preprocessing and modeling pipeline
    model_pipeline = Pipeline(steps=[
        ('preprocessor', numeric_transformer),
        ('classifier', RandomForestClassifier(random_state=42))
    ])
    
    # Hyperparameter tuning
    print("Training model with hyperparameter tuning (this may take a few minutes)...")
    param_grid = {
        'classifier__n_estimators': [100, 200, 300],
        'classifier__max_depth': [None, 10, 20, 30],
        'classifier__min_samples_split': [2, 5, 10],
        'classifier__min_samples_leaf': [1, 2, 4],
        'classifier__bootstrap': [True, False],
        'classifier__max_features': ['sqrt', 'log2']
    }
    
    # Use context manager to properly handle multiprocessing cleanup
    import os
    # Set environment variable to avoid multiprocessing issues on Python 3.13+
    cpu_count = os.cpu_count()
    if cpu_count:
        os.environ['LOKY_MAX_CPU_COUNT'] = str(max(1, cpu_count - 1))
    
    grid_search = GridSearchCV(model_pipeline, param_grid, cv=5, n_jobs=-1, verbose=0)
    grid_search.fit(X_train, y_train)
    
    print(f"Best parameters: {grid_search.best_params_}")
    best_model = grid_search.best_estimator_
    
    # Evaluate on test data
    y_pred = best_model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    print(f"Model accuracy on test data: {accuracy:.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))
    
    # Cross-validation score
    cv_scores = cross_val_score(best_model, X, y, cv=5)
    print(f"\nCross-validation accuracy: {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")
    
    # Feature importance
    feature_importance = best_model.named_steps['classifier'].feature_importances_
    sorted_idx = np.argsort(feature_importance)
    
    plt.figure(figsize=(10, 8))
    plt.barh(range(len(sorted_idx)), feature_importance[sorted_idx], align='center')
    plt.yticks(range(len(sorted_idx)), np.array(features)[sorted_idx])
    plt.title('Feature Importance')
    plt.tight_layout()
    plt.savefig('feature_importance.png', dpi=100, bbox_inches='tight')
    print("\nFeature importance plot saved to 'feature_importance.png'")
    plt.close()
    
    return best_model, features


def make_predictions(best_model, features, upcoming_games):
    """Make predictions on upcoming games."""
    print("\n" + "="*50)
    print("PREDICTING UPCOMING GAMES")
    print("="*50)
    
    # Prepare upcoming games data for prediction
    existing_features = [feature for feature in features if feature in upcoming_games.columns]
    
    # Drop rows with missing values in other features
    upcoming_features = upcoming_games.dropna(subset=existing_features)
    
    # Check if there are any rows left for prediction
    if upcoming_features.empty:
        print("No upcoming games with sufficient data for prediction.")
        return pd.DataFrame()
    
    print(f"Making predictions for {len(upcoming_features)} out of {len(upcoming_games)} upcoming games")
    
    # Fill missing values in other features with 0
    for feature in existing_features:
        if feature not in upcoming_features.columns:
            upcoming_features[feature] = 0
        else:
            upcoming_features.loc[:, feature] = upcoming_features[feature].fillna(0)
    
    # Make predictions
    X_upcoming = upcoming_features[existing_features]
    upcoming_features['home_win_probability'] = best_model.predict_proba(X_upcoming)[:, 1]
    upcoming_features['predicted_winner'] = np.where(
        upcoming_features['home_win_probability'] > 0.5,
        upcoming_features['home_team'],
        upcoming_features['away_team']
    )
    upcoming_features['win_probability'] = np.where(
        upcoming_features['home_win_probability'] > 0.5,
        upcoming_features['home_win_probability'],
        1 - upcoming_features['home_win_probability']
    )
    
    # Sort and display predictions
    required_columns = ['game_day', 'home_team', 'away_team', 'predicted_winner', 'win_probability']
    if all(column in upcoming_features.columns for column in required_columns):
        prediction_results = upcoming_features[required_columns].sort_values('game_day')
        print("\nTop 10 predictions:")
        print(prediction_results.head(10).to_string(index=False))
        return prediction_results
    else:
        print("Required columns for predictions are missing.")
        return pd.DataFrame()


def export_results_and_update_readme(prediction_results, upcoming_features):
    """Export predictions to CSV and update README."""
    print("\n" + "="*50)
    print("EXPORTING RESULTS")
    print("="*50)
    
    # Export predictions to CSV
    if not prediction_results.empty:
        prediction_results.to_csv('NCAA_Game_Predictions.csv', index=False)
        print("Predictions exported to NCAA_Game_Predictions.csv")
    else:
        print("No predictions available to export.")
        return
    
    # Get high confidence predictions
    high_confidence = prediction_results[prediction_results['win_probability'] > 0.8].sort_values(
        'win_probability', ascending=False
    )
    
    # Prepare new README content
    readme_content = [
        '# NCAA Game Predictions\n\n',
        'This project aims to predict the outcomes of NCAA basketball games using machine learning models. '
        'The code leverages the `scikit-learn` library for building and evaluating the models, and '
        'ESPN\'s API for fetching game data.\n\n',
        '## High Confidence Predictions:\n'
    ]
    
    if not high_confidence.empty:
        # Format high confidence predictions with readable headers
        high_confidence = high_confidence.rename(columns={
            'game_day': 'Game Day',
            'home_team': 'Home Team',
            'away_team': 'Away Team',
            'predicted_winner': 'Predicted Winner',
            'win_probability': 'Win Probability'
        })
        
        # Round Win Probability to 2 decimal places
        high_confidence['Win Probability'] = high_confidence['Win Probability'].round(2)
        
        # Convert high confidence predictions to a Markdown table
        high_confidence_table = high_confidence.head(10).to_markdown(index=False)
        
        # Add high confidence predictions to README content
        readme_content.append(high_confidence_table)
    else:
        # Add a note if no highly confident predictions were made
        readme_content.append("No highly confident predictions were made for the upcoming games.\n\n")
    
    # Add the new description and libraries used content at the bottom
    description_content = [
        '## Description\n\n',
        'The main functionalities of this project include:\n\n',
        '- Fetching NCAA basketball game data using ESPN\'s API.\n',
        '- Preprocessing the data for model training.\n',
        '- Building and evaluating machine learning models using `scikit-learn`.\n',
        '- Generating predictions for upcoming games.\n',
        '- Exporting predictions to [NCAA_Game_Predictions.csv](NCAA_Game_Predictions.csv).\n',
        '- Updating the README file with the latest model performance and high confidence predictions.\n\n',
        '## Libraries Used\n\n',
        '- [scikit-learn](https://scikit-learn.org/stable/): A machine learning library for Python that provides '
        'simple and efficient tools for data mining and data analysis.\n',
        '- [ESPN API](https://www.espn.com/apis/devcenter/docs/): Free API for fetching sports data '
        'including NCAA basketball games.\n\n'
    ]
    
    # Add the last updated date and time
    last_updated = datetime.datetime.now().strftime("%B %d, %Y at %I:%M %p")
    last_updated_content = [f'**Last updated:** {last_updated}\n']
    
    # Combine all content
    readme_content += description_content + last_updated_content
    
    # Write the new README content to the file
    with open('README.md', 'w') as file:
        file.writelines(readme_content)
    print("README.md updated with latest model performance and high confidence predictions.")
    
    # Create visualization of prediction distribution
    if 'win_probability' in upcoming_features.columns and not upcoming_features.empty:
        plt.figure(figsize=(10, 6))
        sns.histplot(upcoming_features['win_probability'], bins=20)
        plt.title('Distribution of Win Probabilities')
        plt.xlabel('Win Probability')
        plt.ylabel('Count')
        plt.axvline(0.5, color='red', linestyle='--', alpha=0.7)
        plt.grid(True, alpha=0.3)
        plt.savefig('win_probability_distribution.png', dpi=100, bbox_inches='tight')
        print("Win probability distribution plot saved to 'win_probability_distribution.png'")
        plt.close()


def main():
    """Main function to orchestrate the prediction workflow."""
    print("\n" + "="*60)
    print("NCAA BASKETBALL GAME PREDICTION MODEL")
    print("="*60)
    
    try:
        # Load data
        completed_games, upcoming_games = load_data()
        
        # Explore data
        explore_data(completed_games, upcoming_games)
        
        # Preprocess data
        completed_games, upcoming_games = preprocess_data(completed_games, upcoming_games)
        
        # Calculate team statistics
        team_stats = calculate_team_stats(completed_games)
        
        # Add team stats to both datasets
        completed_games = add_team_stats(completed_games, team_stats)
        upcoming_games = add_team_stats(upcoming_games, team_stats)
        
        # Create model features
        completed_games = create_model_features(completed_games)
        upcoming_games = create_model_features(upcoming_games)
        
        # Build and train model
        best_model, features = build_and_train_model(completed_games)
        
        # Make predictions
        prediction_results = make_predictions(best_model, features, upcoming_games)
        
        # Export results and update README
        if not prediction_results.empty:
            # Need to get upcoming_features for visualization
            existing_features = [feature for feature in features if feature in upcoming_games.columns]
            upcoming_features = upcoming_games.dropna(subset=existing_features)
            for feature in existing_features:
                if feature in upcoming_features.columns:
                    upcoming_features.loc[:, feature] = upcoming_features[feature].fillna(0)
            
            export_results_and_update_readme(prediction_results, upcoming_features)
        
        print("\n" + "="*60)
        print("PREDICTION WORKFLOW COMPLETED SUCCESSFULLY!")
        print("="*60)
        
    finally:
        # Clean up matplotlib and multiprocessing resources
        import matplotlib.pyplot as plt
        plt.close('all')
        
        # Force cleanup of any remaining multiprocessing resources
        import gc
        gc.collect()


if __name__ == "__main__":
    import sys
    import io
    
    # Capture and filter stderr to hide multiprocessing cleanup warnings
    # These are harmless Python 3.13 warnings that appear after the script completes
    original_stderr = sys.stderr
    
    try:
        main()
    finally:
        # Give a moment for any background processes to complete
        import time
        time.sleep(0.1)
        
        # Redirect stderr briefly to suppress cleanup warnings
        sys.stderr = io.StringIO()
        time.sleep(0.1)
        sys.stderr = original_stderr
