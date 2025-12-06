#!/usr/bin/env python3
"""
Feature Selection Analysis

Analyzes feature importance and identifies features to remove:
1. Permutation importance on validation set
2. Correlation analysis (multicollinearity)
3. Feature importance from trained model
4. Remove low-value features

Goal: Reduce from 40+ features to 20-25 core features
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.repositories.games_repository import GamesRepository
from backend.database import get_db_connection
from model_training.adaptive_predictor import AdaptivePredictor
from sklearn.inspection import permutation_importance
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns


def calculate_vif(df, features):
    """
    Calculate Variance Inflation Factor for multicollinearity.
    VIF > 5 indicates high multicollinearity.
    """
    from statsmodels.stats.outliers_influence import variance_inflation_factor
    
    vif_data = pd.DataFrame()
    vif_data["feature"] = features
    vif_data["VIF"] = [
        variance_inflation_factor(df[features].values, i) 
        for i in range(len(features))
    ]
    
    return vif_data.sort_values('VIF', ascending=False)


def analyze_features():
    """Comprehensive feature analysis."""
    
    print("="*80)
    print("FEATURE SELECTION ANALYSIS")
    print("="*80)
    print()
    
    # Load data
    db = get_db_connection()
    games_repo = GamesRepository(db)
    
    print("Loading completed games...")
    completed_games = games_repo.get_completed_games_df()
    
    # Use current season
    current_season = completed_games[completed_games['season'] == '2025-26'].copy()
    
    print(f"  Current season (2025-26): {len(current_season):,} games")
    print()
    
    # Train model with validation split
    print("Training model with validation split...")
    model = AdaptivePredictor(
        use_smart_encoding=True,
        use_early_season_adjustment=True,
        calibrate=True
    )
    
    # Use more data for training, less for validation
    train_data = current_season.iloc[:-100].copy()
    val_data = current_season.iloc[-100:].copy()
    
    print(f"  Training: {len(train_data)} games")
    print(f"  Validation: {len(val_data)} games")
    print()
    
    model.fit(train_data, use_validation=True, val_days=14)
    
    # ================================================================
    # 1. Model Feature Importance (from trained model)
    # ================================================================
    print("\n" + "="*80)
    print("1. MODEL FEATURE IMPORTANCE (Built-in)")
    print("="*80)
    print()
    
    if hasattr(model._raw_model, 'feature_importances_'):
        feature_names = model._raw_model.feature_names_in_
        importances = model._raw_model.feature_importances_
        
        importance_df = pd.DataFrame({
            'feature': feature_names,
            'importance': importances
        }).sort_values('importance', ascending=False)
        
        print(f"Total features: {len(feature_names)}")
        print()
        print("Top 15 features:")
        print(importance_df.head(15).to_string(index=False))
        print()
        
        # Bottom features
        print("Bottom 10 features (candidates for removal):")
        print(importance_df.tail(10).to_string(index=False))
        print()
        
        # Features with importance < 0.01
        low_importance = importance_df[importance_df['importance'] < 0.01]
        print(f"Features with importance < 0.01: {len(low_importance)}")
        if len(low_importance) > 0:
            print(low_importance.to_string(index=False))
        print()
    
    # ================================================================
    # 2. Permutation Importance (on validation set)
    # ================================================================
    print("\n" + "="*80)
    print("2. PERMUTATION IMPORTANCE (Validation Set)")
    print("="*80)
    print()
    print("Calculating permutation importance (this may take a minute)...")
    
    # Prepare validation data
    val_prepared = model.prepare_data(val_data.copy())
    y_val = val_prepared['home_win']
    
    # Get features
    trained_features = model._raw_model.feature_names_in_
    X_val = val_prepared.reindex(columns=list(trained_features), fill_value=0)
    
    # Calculate permutation importance
    perm_importance = permutation_importance(
        model._raw_model,
        X_val,
        y_val,
        n_repeats=10,
        random_state=42,
        n_jobs=-1
    )
    
    perm_df = pd.DataFrame({
        'feature': trained_features,
        'importance_mean': perm_importance.importances_mean,
        'importance_std': perm_importance.importances_std
    }).sort_values('importance_mean', ascending=False)
    
    print("\nTop 15 features (by permutation importance):")
    print(perm_df.head(15).to_string(index=False))
    print()
    
    print("Bottom 10 features (candidates for removal):")
    print(perm_df.tail(10).to_string(index=False))
    print()
    
    # Features with importance < 0.001
    low_perm = perm_df[perm_df['importance_mean'] < 0.001]
    print(f"Features with permutation importance < 0.001: {len(low_perm)}")
    if len(low_perm) > 0:
        print(low_perm.to_string(index=False))
    print()
    
    # ================================================================
    # 3. Feature Correlation Analysis
    # ================================================================
    print("\n" + "="*80)
    print("3. FEATURE CORRELATION ANALYSIS")
    print("="*80)
    print()
    
    # Get numeric features only
    numeric_cols = X_val.select_dtypes(include=[np.number]).columns
    correlation_matrix = X_val[numeric_cols].corr()
    
    # Find highly correlated pairs
    high_corr_pairs = []
    for i in range(len(correlation_matrix.columns)):
        for j in range(i+1, len(correlation_matrix.columns)):
            corr = correlation_matrix.iloc[i, j]
            if abs(corr) > 0.85:  # High correlation threshold
                high_corr_pairs.append({
                    'feature1': correlation_matrix.columns[i],
                    'feature2': correlation_matrix.columns[j],
                    'correlation': corr
                })
    
    if high_corr_pairs:
        high_corr_df = pd.DataFrame(high_corr_pairs).sort_values('correlation', 
                                                                   ascending=False, 
                                                                   key=abs)
        print(f"Highly correlated feature pairs (|r| > 0.85): {len(high_corr_pairs)}")
        print()
        print(high_corr_df.to_string(index=False))
        print()
        print("Recommendation: Consider removing one from each pair")
    else:
        print("No highly correlated feature pairs found (|r| > 0.85)")
    print()
    
    # ================================================================
    # 4. Variance Inflation Factor (Multicollinearity)
    # ================================================================
    print("\n" + "="*80)
    print("4. MULTICOLLINEARITY ANALYSIS (VIF)")
    print("="*80)
    print()
    
    try:
        # Sample data for VIF calculation (expensive)
        X_sample = X_val[numeric_cols].sample(min(500, len(X_val)), random_state=42)
        
        # Remove any columns with zero variance
        X_sample = X_sample.loc[:, X_sample.std() > 0]
        
        print("Calculating VIF (Variance Inflation Factor)...")
        print("VIF > 10: High multicollinearity")
        print("VIF > 5: Moderate multicollinearity")
        print()
        
        vif_df = calculate_vif(X_sample, X_sample.columns.tolist())
        
        print("Features with VIF > 5:")
        high_vif = vif_df[vif_df['VIF'] > 5]
        if len(high_vif) > 0:
            print(high_vif.to_string(index=False))
        else:
            print("None - all features have VIF < 5")
        print()
        
    except Exception as e:
        print(f"VIF calculation failed: {e}")
        print("Skipping multicollinearity analysis")
        print()
    
    # ================================================================
    # 5. Feature Selection Recommendations
    # ================================================================
    print("\n" + "="*80)
    print("5. FEATURE SELECTION RECOMMENDATIONS")
    print("="*80)
    print()
    
    # Combine analyses to recommend features to remove
    features_to_remove = set()
    features_to_keep = set()
    
    # Rule 1: Remove features with model importance < 0.005
    if hasattr(model._raw_model, 'feature_importances_'):
        low_model_imp = importance_df[importance_df['importance'] < 0.005]['feature'].tolist()
        features_to_remove.update(low_model_imp)
        print(f"Rule 1: Features with model importance < 0.005: {len(low_model_imp)}")
        if low_model_imp:
            print(f"  {', '.join(low_model_imp[:5])}{'...' if len(low_model_imp) > 5 else ''}")
        print()
    
    # Rule 2: Remove features with permutation importance < 0.0005
    low_perm_imp = perm_df[perm_df['importance_mean'] < 0.0005]['feature'].tolist()
    features_to_remove.update(low_perm_imp)
    print(f"Rule 2: Features with permutation importance < 0.0005: {len(low_perm_imp)}")
    if low_perm_imp:
        print(f"  {', '.join(low_perm_imp[:5])}{'...' if len(low_perm_imp) > 5 else ''}")
    print()
    
    # Rule 3: For highly correlated pairs, keep the one with higher importance
    if high_corr_pairs:
        for pair in high_corr_pairs:
            f1, f2 = pair['feature1'], pair['feature2']
            if f1 in importance_df['feature'].values and f2 in importance_df['feature'].values:
                imp1 = importance_df[importance_df['feature'] == f1]['importance'].iloc[0]
                imp2 = importance_df[importance_df['feature'] == f2]['importance'].iloc[0]
                
                if imp1 < imp2:
                    features_to_remove.add(f1)
                else:
                    features_to_remove.add(f2)
        
        print(f"Rule 3: One feature from each highly correlated pair")
        print()
    
    # Always keep the most important features
    top_features = importance_df.head(15)['feature'].tolist()
    features_to_keep.update(top_features)
    
    # Remove conflicts
    features_to_remove = features_to_remove - features_to_keep
    
    print(f"Current features: {len(trained_features)}")
    print(f"Recommended to remove: {len(features_to_remove)}")
    print(f"Remaining features: {len(trained_features) - len(features_to_remove)}")
    print()
    
    if features_to_remove:
        print("Features recommended for removal:")
        for i, feat in enumerate(sorted(features_to_remove), 1):
            print(f"  {i:2}. {feat}")
        print()
    
    # Save recommendations
    output_path = 'data/feature_selection_recommendations.json'
    recommendations = {
        'total_features': len(trained_features),
        'features_to_remove': sorted(list(features_to_remove)),
        'features_to_keep': sorted(list(set(trained_features) - features_to_remove)),
        'top_15_features': top_features,
        'analysis_date': pd.Timestamp.now().isoformat()
    }
    
    import json
    os.makedirs('data', exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(recommendations, f, indent=2)
    
    print(f"Recommendations saved to: {output_path}")
    print()
    
    # ================================================================
    # 6. Visualizations
    # ================================================================
    print("\n" + "="*80)
    print("6. GENERATING VISUALIZATIONS")
    print("="*80)
    print()
    
    # Feature importance plot
    fig, axes = plt.subplots(2, 1, figsize=(12, 10))
    
    # Model importance
    top_20 = importance_df.head(20)
    axes[0].barh(range(len(top_20)), top_20['importance'])
    axes[0].set_yticks(range(len(top_20)))
    axes[0].set_yticklabels(top_20['feature'])
    axes[0].set_xlabel('Feature Importance')
    axes[0].set_title('Top 20 Features (Model Importance)', fontweight='bold')
    axes[0].invert_yaxis()
    axes[0].grid(True, alpha=0.3, axis='x')
    
    # Permutation importance
    top_20_perm = perm_df.head(20)
    axes[1].barh(range(len(top_20_perm)), top_20_perm['importance_mean'])
    axes[1].set_yticks(range(len(top_20_perm)))
    axes[1].set_yticklabels(top_20_perm['feature'])
    axes[1].set_xlabel('Permutation Importance')
    axes[1].set_title('Top 20 Features (Permutation Importance)', fontweight='bold')
    axes[1].invert_yaxis()
    axes[1].grid(True, alpha=0.3, axis='x')
    
    plt.tight_layout()
    
    viz_path = 'docs/feature_importance_analysis.png'
    plt.savefig(viz_path, dpi=150, bbox_inches='tight')
    print(f"Feature importance plot saved to: {viz_path}")
    
    # Correlation heatmap for top features
    if len(top_features) > 5:
        fig, ax = plt.subplots(figsize=(12, 10))
        
        # Get correlation for top features
        top_corr = correlation_matrix.loc[top_features[:20], top_features[:20]]
        
        sns.heatmap(top_corr, annot=True, fmt='.2f', cmap='coolwarm', 
                    center=0, square=True, ax=ax, cbar_kws={'label': 'Correlation'})
        ax.set_title('Correlation Heatmap - Top 20 Features', fontweight='bold', pad=20)
        
        plt.tight_layout()
        
        corr_path = 'docs/feature_correlation_heatmap.png'
        plt.savefig(corr_path, dpi=150, bbox_inches='tight')
        print(f"Correlation heatmap saved to: {corr_path}")
    
    print()
    print("="*80)
    print("FEATURE ANALYSIS COMPLETE")
    print("="*80)
    
    db.close()


if __name__ == '__main__':
    analyze_features()
