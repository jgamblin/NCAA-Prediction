#!/usr/bin/env python3
"""
Ensemble Predictor for NCAA Basketball Games (Phase 3)

Combines multiple model architectures for more robust predictions:
- XGBoost (gradient boosting)
- RandomForest (bagging)
- LogisticRegression (linear baseline)

Phase 3 Implementation - November 29, 2025:
- Task 3.1: XGBoost integration with optimized hyperparameters
- Task 3.2: Proper temporal train/validation split
- Task 3.3: Weighted model ensemble
"""

import pandas as pd
import numpy as np
import sys
import os
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any

from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.calibration import CalibratedClassifierCV
from sklearn.isotonic import IsotonicRegression

# Try to import XGBoost
try:
    import xgboost as xgb
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False
    print("Warning: XGBoost not installed. Install with: pip install xgboost")

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load feature flags
try:
    with open(Path('config') / 'feature_flags.json') as f:
        _feature_flags = json.load(f)
except Exception:
    _feature_flags = {}


class EnsemblePredictor:
    """
    Ensemble model combining XGBoost, RandomForest, and LogisticRegression.
    
    Uses weighted averaging of predictions with proper temporal validation.
    """
    
    # Default model weights (sum to 1.0)
    DEFAULT_WEIGHTS = {
        'xgboost': 0.45,
        'random_forest': 0.35,
        'logistic': 0.20,
    }
    
    # Default XGBoost parameters (tuned for NCAA prediction)
    DEFAULT_XGB_PARAMS = {
        'n_estimators': 200,
        'max_depth': 6,
        'learning_rate': 0.1,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'min_child_weight': 3,
        'gamma': 0.1,
        'reg_alpha': 0.1,
        'reg_lambda': 1.0,
        'objective': 'binary:logistic',
        'eval_metric': 'logloss',
        'random_state': 42,
        'n_jobs': -1,
        'verbosity': 0,
    }
    
    # Default RandomForest parameters
    DEFAULT_RF_PARAMS = {
        'n_estimators': 150,
        'max_depth': 12,
        'min_samples_split': 15,
        'min_samples_leaf': 5,
        'random_state': 42,
        'n_jobs': -1,
    }
    
    # Default LogisticRegression parameters
    DEFAULT_LR_PARAMS = {
        'max_iter': 1000,
        'C': 1.0,
        'solver': 'lbfgs',
        'random_state': 42,
    }
    
    def __init__(
        self,
        weights: Dict[str, float] = None,
        xgb_params: Dict[str, Any] = None,
        rf_params: Dict[str, Any] = None,
        lr_params: Dict[str, Any] = None,
        use_xgboost: bool = True,
        use_random_forest: bool = True,
        use_logistic: bool = True,
        validation_days: int = 14,
        calibrate: bool = True,
        feature_importance_path: str = 'data/Ensemble_Feature_Importance.csv',
    ):
        """
        Initialize the ensemble predictor.
        
        Args:
            weights: Model weights for ensemble (must sum to ~1.0)
            xgb_params: XGBoost hyperparameters
            rf_params: RandomForest hyperparameters
            lr_params: LogisticRegression hyperparameters
            use_xgboost: Include XGBoost in ensemble
            use_random_forest: Include RandomForest in ensemble
            use_logistic: Include LogisticRegression in ensemble
            validation_days: Days to hold out for validation
            calibrate: Whether to calibrate probabilities
            feature_importance_path: Path to save feature importance
        """
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
        self.xgb_params = {**self.DEFAULT_XGB_PARAMS, **(xgb_params or {})}
        self.rf_params = {**self.DEFAULT_RF_PARAMS, **(rf_params or {})}
        self.lr_params = {**self.DEFAULT_LR_PARAMS, **(lr_params or {})}
        
        self.use_xgboost = use_xgboost and HAS_XGBOOST
        self.use_random_forest = use_random_forest
        self.use_logistic = use_logistic
        self.validation_days = validation_days
        self.calibrate = calibrate
        self.feature_importance_path = feature_importance_path
        
        # Models storage
        self.models: Dict[str, Any] = {}
        self.calibrators: Dict[str, Any] = {}
        self.scaler: Optional[StandardScaler] = None
        self.team_encoder = LabelEncoder()
        
        # Feature columns
        self.feature_cols: List[str] = []
        self.trained_feature_cols: List[str] = []
        
        # Validation metrics
        self.validation_accuracy: Dict[str, float] = {}
        self.validation_log_loss: Dict[str, float] = {}
        
        # Normalize weights based on enabled models
        self._normalize_weights()
    
    def _normalize_weights(self):
        """Normalize weights to sum to 1.0 based on enabled models."""
        active_weights = {}
        
        if self.use_xgboost:
            active_weights['xgboost'] = self.weights.get('xgboost', 0.45)
        if self.use_random_forest:
            active_weights['random_forest'] = self.weights.get('random_forest', 0.35)
        if self.use_logistic:
            active_weights['logistic'] = self.weights.get('logistic', 0.20)
        
        total = sum(active_weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in active_weights.items()}
        else:
            # Fallback to random forest only
            self.use_random_forest = True
            self.weights = {'random_forest': 1.0}
    
    def _create_xgboost_model(self) -> Any:
        """Create XGBoost classifier with optimized parameters."""
        if not HAS_XGBOOST:
            raise ImportError("XGBoost not installed")
        
        return xgb.XGBClassifier(**self.xgb_params)
    
    def _create_rf_model(self) -> RandomForestClassifier:
        """Create RandomForest classifier."""
        return RandomForestClassifier(**self.rf_params)
    
    def _create_lr_model(self) -> LogisticRegression:
        """Create LogisticRegression classifier."""
        return LogisticRegression(**self.lr_params)
    
    def create_temporal_split(
        self, 
        df: pd.DataFrame, 
        val_days: int = None
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Create train/validation split respecting temporal order.
        
        Uses most recent 'val_days' of data for validation.
        This prevents data leakage by simulating real prediction scenario.
        
        Args:
            df: Full dataset with 'date' column
            val_days: Days to hold out for validation (default: self.validation_days)
            
        Returns:
            (train_df, val_df) tuple
        """
        if val_days is None:
            val_days = self.validation_days
        
        df = df.copy()
        
        # Ensure date column exists and is datetime
        if 'date' not in df.columns:
            if 'Date' in df.columns:
                df['date'] = df['Date']
            else:
                # No date column - fall back to random split warning
                print("  Warning: No date column found, using random 80/20 split")
                n = len(df)
                train_size = int(n * 0.8)
                return df.iloc[:train_size], df.iloc[train_size:]
        
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df = df.dropna(subset=['date'])
        df = df.sort_values('date')
        
        max_date = df['date'].max()
        val_cutoff = max_date - timedelta(days=val_days)
        
        train_mask = df['date'] < val_cutoff
        val_mask = df['date'] >= val_cutoff
        
        train_df = df[train_mask]
        val_df = df[val_mask]
        
        print(f"  Temporal split: {len(train_df)} train, {len(val_df)} validation (last {val_days} days)")
        
        return train_df, val_df
    
    def fit(self, df: pd.DataFrame, feature_cols: List[str] = None) -> 'EnsemblePredictor':
        """
        Train the ensemble on historical data with temporal validation.
        
        Args:
            df: Training data with features and 'home_win' target
            feature_cols: List of feature columns to use
            
        Returns:
            self for method chaining
        """
        print("Training ensemble predictor (Phase 3)...")
        
        # Create temporal split
        train_df, val_df = self.create_temporal_split(df)
        
        if len(train_df) < 100:
            print("  Warning: Small training set, reducing validation period")
            train_df, val_df = self.create_temporal_split(df, val_days=7)
        
        if len(val_df) < 20:
            print("  Warning: Small validation set, merging with training")
            train_df = df
            val_df = df.tail(min(50, len(df) // 5))
        
        # Prepare features
        if feature_cols:
            self.feature_cols = feature_cols
        else:
            # Auto-detect numeric feature columns
            self.feature_cols = self._detect_feature_cols(train_df)
        
        X_train, y_train = self._prepare_features(train_df)
        X_val, y_val = self._prepare_features(val_df)
        
        self.trained_feature_cols = list(X_train.columns)
        
        # Scale features for logistic regression
        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_val_scaled = self.scaler.transform(X_val)
        
        # Train each model
        print("  Training individual models...")
        
        if self.use_xgboost:
            self._train_xgboost(X_train, y_train, X_val, y_val)
        
        if self.use_random_forest:
            self._train_random_forest(X_train, y_train, X_val, y_val)
        
        if self.use_logistic:
            self._train_logistic(X_train_scaled, y_train, X_val_scaled, y_val)
        
        # Calibrate on validation set
        if self.calibrate:
            self._calibrate_models(X_val, X_val_scaled, y_val)
        
        # Log ensemble performance
        self._log_ensemble_performance(X_val, X_val_scaled, y_val)
        
        # Save feature importance
        self._save_feature_importance()
        
        return self
    
    def _detect_feature_cols(self, df: pd.DataFrame) -> List[str]:
        """Auto-detect numeric feature columns."""
        exclude = ['game_id', 'date', 'home_team', 'away_team', 'home_score', 
                   'away_score', 'home_win', 'season', 'game_url', 'game_status']
        
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        feature_cols = [c for c in numeric_cols if c not in exclude and not c.endswith('_id')]
        
        return feature_cols
    
    def _prepare_features(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """Prepare feature matrix and target."""
        df = df.copy()
        
        # Ensure target exists
        if 'home_win' not in df.columns:
            if 'home_score' in df.columns and 'away_score' in df.columns:
                df['home_win'] = (df['home_score'] > df['away_score']).astype(int)
            else:
                raise ValueError("Cannot determine target: need 'home_win' or scores")
        
        # Select available features
        available_cols = [c for c in self.feature_cols if c in df.columns]
        
        if not available_cols:
            raise ValueError(f"No feature columns found. Expected: {self.feature_cols[:5]}...")
        
        X = df[available_cols].copy()
        y = df['home_win'].copy()
        
        # Fill NaN with 0 (features should be pre-processed, but safety)
        X = X.fillna(0)
        
        return X, y
    
    def _train_xgboost(self, X_train, y_train, X_val, y_val):
        """Train XGBoost model."""
        print("    Training XGBoost...")
        
        model = self._create_xgboost_model()
        
        # Train with early stopping if validation set available
        if len(X_val) > 0:
            model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                verbose=False
            )
        else:
            model.fit(X_train, y_train)
        
        self.models['xgboost'] = model
        
        # Validation metrics
        if len(X_val) > 0:
            val_pred = model.predict(X_val)
            val_proba = model.predict_proba(X_val)[:, 1]
            accuracy = (val_pred == y_val).mean()
            self.validation_accuracy['xgboost'] = accuracy
            print(f"      XGBoost validation accuracy: {accuracy:.1%}")
    
    def _train_random_forest(self, X_train, y_train, X_val, y_val):
        """Train RandomForest model."""
        print("    Training RandomForest...")
        
        model = self._create_rf_model()
        model.fit(X_train, y_train)
        
        self.models['random_forest'] = model
        
        # Validation metrics
        if len(X_val) > 0:
            val_pred = model.predict(X_val)
            accuracy = (val_pred == y_val).mean()
            self.validation_accuracy['random_forest'] = accuracy
            print(f"      RandomForest validation accuracy: {accuracy:.1%}")
    
    def _train_logistic(self, X_train_scaled, y_train, X_val_scaled, y_val):
        """Train LogisticRegression model."""
        print("    Training LogisticRegression...")
        
        model = self._create_lr_model()
        model.fit(X_train_scaled, y_train)
        
        self.models['logistic'] = model
        
        # Validation metrics
        if len(X_val_scaled) > 0:
            val_pred = model.predict(X_val_scaled)
            accuracy = (val_pred == y_val).mean()
            self.validation_accuracy['logistic'] = accuracy
            print(f"      LogisticRegression validation accuracy: {accuracy:.1%}")
    
    def _calibrate_models(self, X_val, X_val_scaled, y_val):
        """Calibrate model probabilities using isotonic regression on validation set."""
        print("    Calibrating probabilities...")
        
        for name, model in self.models.items():
            try:
                if name == 'logistic':
                    proba = model.predict_proba(X_val_scaled)[:, 1]
                else:
                    proba = model.predict_proba(X_val)[:, 1]
                
                calibrator = IsotonicRegression(out_of_bounds='clip')
                calibrator.fit(proba, y_val)
                self.calibrators[name] = calibrator
            except Exception as e:
                print(f"      Warning: Calibration failed for {name}: {e}")
    
    def _log_ensemble_performance(self, X_val, X_val_scaled, y_val):
        """Log ensemble performance on validation set."""
        if len(y_val) == 0:
            return
        
        # Get ensemble predictions
        proba = self._ensemble_predict_proba(X_val, X_val_scaled)
        pred = (proba > 0.5).astype(int)
        accuracy = (pred == y_val).mean()
        
        print(f"  Ensemble validation accuracy: {accuracy:.1%}")
        self.validation_accuracy['ensemble'] = accuracy
        
        # Compare to individual models
        best_individual = max(
            [(k, v) for k, v in self.validation_accuracy.items() if k != 'ensemble'],
            key=lambda x: x[1]
        )
        print(f"  Best individual model: {best_individual[0]} ({best_individual[1]:.1%})")
        
        if accuracy >= best_individual[1]:
            print(f"  ✓ Ensemble matches or beats best individual model")
        else:
            print(f"  Note: Individual model slightly better (ensemble: {accuracy:.1%})")
    
    def _ensemble_predict_proba(self, X, X_scaled=None) -> np.ndarray:
        """Get weighted ensemble probability predictions."""
        weighted_proba = np.zeros(len(X))
        total_weight = 0
        
        for name, model in self.models.items():
            weight = self.weights.get(name, 0)
            if weight <= 0:
                continue
            
            # Get raw probabilities
            if name == 'logistic':
                if X_scaled is None:
                    X_scaled = self.scaler.transform(X)
                proba = model.predict_proba(X_scaled)[:, 1]
            else:
                proba = model.predict_proba(X)[:, 1]
            
            # Apply calibration if available
            if name in self.calibrators:
                proba = self.calibrators[name].predict(proba)
            
            weighted_proba += proba * weight
            total_weight += weight
        
        if total_weight > 0:
            weighted_proba /= total_weight
        
        return np.clip(weighted_proba, 0.01, 0.99)
    
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """
        Get probability predictions from ensemble.
        
        Args:
            X: Feature matrix (DataFrame with feature columns)
            
        Returns:
            Array of shape (n_samples, 2) with [away_win_prob, home_win_prob]
        """
        # Align features
        X_aligned = self._align_features(X)
        
        # Scale for logistic regression
        X_scaled = self.scaler.transform(X_aligned) if self.scaler else X_aligned
        
        # Get ensemble probabilities
        home_proba = self._ensemble_predict_proba(X_aligned, X_scaled)
        
        return np.column_stack([1 - home_proba, home_proba])
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Get class predictions (0 = away win, 1 = home win)."""
        proba = self.predict_proba(X)
        return (proba[:, 1] > 0.5).astype(int)
    
    def _align_features(self, X: pd.DataFrame) -> pd.DataFrame:
        """Align feature columns to trained features."""
        X = X.copy()
        
        # Add missing columns with 0
        for col in self.trained_feature_cols:
            if col not in X.columns:
                X[col] = 0
        
        # Select only trained columns in correct order
        return X[self.trained_feature_cols].fillna(0)
    
    def _save_feature_importance(self):
        """Save combined feature importance from all models."""
        importance_data = {}
        
        for name, model in self.models.items():
            if hasattr(model, 'feature_importances_'):
                for i, col in enumerate(self.trained_feature_cols):
                    if col not in importance_data:
                        importance_data[col] = {}
                    importance_data[col][name] = model.feature_importances_[i]
            elif hasattr(model, 'coef_'):
                # Logistic regression uses absolute coefficients
                for i, col in enumerate(self.trained_feature_cols):
                    if col not in importance_data:
                        importance_data[col] = {}
                    importance_data[col][name] = abs(model.coef_[0][i])
        
        if not importance_data:
            return
        
        # Create DataFrame
        rows = []
        for col, importances in importance_data.items():
            row = {'feature': col}
            weighted_sum = 0
            for model_name, imp in importances.items():
                row[f'{model_name}_importance'] = imp
                weighted_sum += imp * self.weights.get(model_name, 0)
            row['weighted_importance'] = weighted_sum
            rows.append(row)
        
        imp_df = pd.DataFrame(rows)
        imp_df = imp_df.sort_values('weighted_importance', ascending=False)
        
        # Save
        os.makedirs(os.path.dirname(self.feature_importance_path), exist_ok=True)
        imp_df.to_csv(self.feature_importance_path, index=False)
        
        # Print top features
        print("  Top ensemble features:")
        for _, row in imp_df.head(8).iterrows():
            print(f"    {row['feature']}: {row['weighted_importance']:.4f}")
    
    def get_model_weights(self) -> Dict[str, float]:
        """Get current model weights."""
        return self.weights.copy()
    
    def set_model_weights(self, weights: Dict[str, float]):
        """Set new model weights (will be normalized)."""
        self.weights = weights
        self._normalize_weights()


def create_ensemble_from_adaptive(adaptive_predictor) -> EnsemblePredictor:
    """
    Create an EnsemblePredictor from an existing AdaptivePredictor's training data.
    
    This allows gradual migration from the old model to the new ensemble.
    """
    ensemble = EnsemblePredictor()
    
    if hasattr(adaptive_predictor, 'training_data') and adaptive_predictor.training_data is not None:
        # Get feature columns from adaptive predictor
        feature_cols = getattr(adaptive_predictor, 'feature_cols', None)
        ensemble.fit(adaptive_predictor.training_data, feature_cols=feature_cols)
    
    return ensemble


__all__ = ['EnsemblePredictor', 'create_ensemble_from_adaptive', 'HAS_XGBOOST']
