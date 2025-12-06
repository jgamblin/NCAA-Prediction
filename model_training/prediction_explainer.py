"""
Prediction Explainer - Generate plain English explanations for predictions

Uses feature importance and feature values to create human-readable explanations
without requiring LLM calls.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple


class PredictionExplainer:
    """Generate natural language explanations for predictions."""
    
    # Feature descriptions and thresholds
    # Templates use no subject - will be added in context
    FEATURE_TEMPLATES = {
        'power_rating_diff': {
            'name': 'Overall Strength',
            'positive_strong': "significantly stronger overall",
            'positive_moderate': "have the edge in overall team strength",
            'positive_weak': "slightly stronger",
        },
        'off_rating_diff': {
            'name': 'Offensive Efficiency',
            'positive_strong': "have a major offensive advantage",
            'positive_moderate': "have a notably better offense",
            'positive_weak': "have a slight offensive edge",
        },
        'def_rating_diff': {
            'name': 'Defensive Efficiency',
            'positive_strong': "have a vastly superior defense",
            'positive_moderate': "have a strong defensive advantage",
            'positive_weak': "have a slightly better defense",
        },
        'venue_wpct_diff': {
            'name': 'Home/Away Performance',
            'positive_strong': "dominant at their home venue",
            'positive_moderate': "perform well at home",
            'positive_weak': "have a slight home court advantage",
        },
        'home_team_home_wpct': {
            'name': 'Home Record',
            'high': "excellent at home this season",
            'medium': "have a solid home record",
            'low': "have struggled at home",
        },
        'away_team_away_wpct': {
            'name': 'Road Record',
            'high': "excellent on the road",
            'medium': "have a decent road record",
            'low': "have struggled on the road",
        },
        'momentum_diff': {
            'name': 'Recent Performance',
            'positive_strong': "playing much better lately",
            'positive_moderate': "have momentum on their side",
            'positive_weak': "playing slightly better recently",
        },
        'sos_diff': {
            'name': 'Strength of Schedule',
            'positive_strong': "have faced much tougher competition",
            'positive_moderate': "have a tougher schedule",
            'positive_weak': "have faced slightly tougher opponents",
        },
        'rest_advantage': {
            'name': 'Rest Days',
            'positive': "more rested",
            'negative': "less rested but still favored",
        },
        'combined_home_adv': {
            'name': 'Home Court Impact',
            'high': "strong home court advantage expected",
            'medium': "moderate home court advantage",
            'low': "minimal home court advantage",
        },
    }
    
    # Thresholds for categorization
    THRESHOLDS = {
        'strong': 0.15,      # 15+ point difference or 0.15 rating difference
        'moderate': 0.08,    # 8-15 point difference
        'weak': 0.03,        # 3-8 point difference
        'wpct_high': 0.70,   # 70%+ win percentage
        'wpct_medium': 0.55, # 55-70% win percentage
    }
    
    def __init__(self, feature_importance: pd.DataFrame = None):
        """
        Initialize explainer.
        
        Args:
            feature_importance: DataFrame with 'feature' and 'importance' columns
        """
        self.feature_importance = feature_importance
        if feature_importance is not None:
            # Create importance lookup
            self.importance_map = dict(zip(
                feature_importance['feature'],
                feature_importance['importance']
            ))
        else:
            self.importance_map = {}
    
    def explain_prediction(
        self,
        home_team: str,
        away_team: str,
        predicted_winner: str,
        confidence: float,
        features: Dict[str, float],
        top_n: int = 3
    ) -> str:
        """
        Generate plain English explanation for a prediction.
        
        Args:
            home_team: Home team name
            away_team: Away team name
            predicted_winner: Predicted winner
            confidence: Model confidence (0-1)
            features: Dictionary of feature names to values
            top_n: Number of top factors to include
            
        Returns:
            Natural language explanation string
        """
        # Determine if home or away is predicted winner
        is_home_winner = (predicted_winner == home_team)
        winner = home_team if is_home_winner else away_team
        loser = away_team if is_home_winner else home_team
        
        # Calculate feature contributions (importance * value)
        contributions = self._calculate_contributions(features, is_home_winner)
        
        # Get top contributing factors
        top_factors = self._get_top_factors(contributions, top_n)
        
        # Generate explanation phrases
        phrases = []
        for feature, value, contribution in top_factors:
            phrase = self._feature_to_phrase(feature, value, winner, loser, is_home_winner)
            if phrase:
                phrases.append(phrase)
        
        # Construct final explanation
        explanation = self._construct_explanation(winner, confidence, phrases)
        
        return explanation
    
    def _calculate_contributions(
        self,
        features: Dict[str, float],
        is_home_winner: bool
    ) -> List[Tuple[str, float, float]]:
        """
        Calculate contribution of each feature to the prediction.
        
        Returns:
            List of (feature_name, feature_value, contribution_score)
        """
        contributions = []
        
        for feature, value in features.items():
            # Get importance (default to 0 if not in map)
            importance = self.importance_map.get(feature, 0)
            
            # Adjust value sign based on predicted winner
            # For diff features: positive = home advantage
            if not is_home_winner and '_diff' in feature:
                value = -value
            
            # Contribution is importance * absolute value
            contribution = importance * abs(value)
            
            contributions.append((feature, value, contribution))
        
        return contributions
    
    def _get_top_factors(
        self,
        contributions: List[Tuple[str, float, float]],
        top_n: int
    ) -> List[Tuple[str, float, float]]:
        """Get top N contributing factors, sorted by contribution."""
        # Filter to only features we have templates for
        relevant = [
            c for c in contributions
            if c[0] in self.FEATURE_TEMPLATES and c[2] > 0.001
        ]
        
        # Sort by contribution (highest first)
        relevant.sort(key=lambda x: x[2], reverse=True)
        
        return relevant[:top_n]
    
    def _feature_to_phrase(
        self,
        feature: str,
        value: float,
        winner: str,
        loser: str,
        is_home_winner: bool
    ) -> str:
        """Convert a feature and its value to a natural language phrase."""
        if feature not in self.FEATURE_TEMPLATES:
            return None
        
        templates = self.FEATURE_TEMPLATES[feature]
        
        # Handle different feature types
        if '_diff' in feature or feature in ['rest_advantage', 'combined_home_adv']:
            # Differential features
            abs_value = abs(value)
            
            if abs_value >= self.THRESHOLDS['strong']:
                level = 'positive_strong'
            elif abs_value >= self.THRESHOLDS['moderate']:
                level = 'positive_moderate'
            elif abs_value >= self.THRESHOLDS['weak']:
                level = 'positive_weak'
            else:
                return None
            
            return templates.get(level)
        
        elif '_wpct' in feature:
            # Win percentage features
            if value >= self.THRESHOLDS['wpct_high']:
                level = 'high'
            elif value >= self.THRESHOLDS['wpct_medium']:
                level = 'medium'
            else:
                level = 'low'
            
            return templates.get(level)
        
        return None
    
    def _construct_explanation(
        self,
        winner: str,
        confidence: float,
        phrases: List[str]
    ) -> str:
        """Construct final explanation from phrases."""
        if not phrases:
            return f"{winner} is favored to win this matchup."
        
        # Add confidence descriptor
        if confidence >= 0.85:
            conf_word = "strongly"
        elif confidence >= 0.75:
            conf_word = "confidently"
        elif confidence >= 0.65:
            conf_word = ""
        else:
            conf_word = "narrowly"
        
        # Start with main statement
        if conf_word:
            intro = f"{winner} is {conf_word} favored"
        else:
            intro = f"{winner} is favored"
        
        # Normalize phrases - add "they" subject consistently
        normalized_phrases = []
        for phrase in phrases:
            # If phrase starts with a verb, add "they"
            if phrase.startswith(('have ', 'perform ')):
                normalized_phrases.append(f"they {phrase}")
            # If phrase starts with present participle (-ing), add "they are"
            elif phrase.startswith('playing '):
                normalized_phrases.append(f"they are {phrase}")
            # If phrase starts with an adjective, add "they are"
            elif phrase.startswith(('dominant ', 'excellent ', 'more ', 'less ', 'significantly ', 'slightly ')):
                normalized_phrases.append(f"they are {phrase}")
            # Otherwise use as-is (probably already has proper structure)
            else:
                normalized_phrases.append(phrase)
        
        # Add reasons with proper grammar
        if len(normalized_phrases) == 1:
            explanation = f"{intro} because {normalized_phrases[0]}."
        elif len(normalized_phrases) == 2:
            explanation = f"{intro}: {normalized_phrases[0]} and {normalized_phrases[1]}."
        else:
            # 3+ phrases
            reasons = ", ".join(normalized_phrases[:-1])
            explanation = f"{intro}: {reasons}, and {normalized_phrases[-1]}."
        
        return explanation


def add_explanations_to_predictions(
    predictions: pd.DataFrame,
    feature_importance: pd.DataFrame,
    game_features: pd.DataFrame
) -> pd.DataFrame:
    """
    Add explanation column to predictions dataframe.
    
    Args:
        predictions: DataFrame with predictions (must have game_id, home_team, away_team, predicted_winner, confidence)
        feature_importance: DataFrame with feature importance scores
        game_features: DataFrame with feature values for each game (indexed by game_id)
        
    Returns:
        Predictions DataFrame with added 'explanation' column
    """
    explainer = PredictionExplainer(feature_importance)
    
    explanations = []
    for _, row in predictions.iterrows():
        game_id = row['game_id']
        
        # Get features for this game
        if game_id in game_features.index:
            features = game_features.loc[game_id].to_dict()
        else:
            features = {}
        
        # Generate explanation
        explanation = explainer.explain_prediction(
            home_team=row['home_team'],
            away_team=row['away_team'],
            predicted_winner=row['predicted_winner'],
            confidence=row['confidence'],
            features=features
        )
        
        explanations.append(explanation)
    
    predictions['explanation'] = explanations
    return predictions


# Example usage
if __name__ == '__main__':
    # Example feature importance
    feature_importance = pd.DataFrame({
        'feature': ['off_rating_diff', 'def_rating_diff', 'power_rating_diff', 'venue_wpct_diff'],
        'importance': [0.25, 0.20, 0.15, 0.12]
    })
    
    explainer = PredictionExplainer(feature_importance)
    
    # Example prediction
    explanation = explainer.explain_prediction(
        home_team="Duke",
        away_team="North Carolina",
        predicted_winner="Duke",
        confidence=0.82,
        features={
            'off_rating_diff': 0.18,      # Duke has big offensive advantage
            'def_rating_diff': 0.05,      # Duke slight defensive edge
            'power_rating_diff': 0.12,    # Duke stronger overall
            'venue_wpct_diff': 0.25,      # Duke dominant at home
            'home_team_home_wpct': 0.88,  # Duke excellent at home
        }
    )
    
    print("Example Explanation:")
    print(explanation)
    print()
    
    # Another example - close game
    explanation2 = explainer.explain_prediction(
        home_team="Wake Forest",
        away_team="Virginia Tech",
        predicted_winner="Wake Forest",
        confidence=0.62,
        features={
            'off_rating_diff': 0.04,
            'def_rating_diff': -0.02,
            'power_rating_diff': 0.05,
            'venue_wpct_diff': 0.15,
            'momentum_diff': 0.08,
        }
    )
    
    print("Example 2 (Close Game):")
    print(explanation2)
