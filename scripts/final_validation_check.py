#!/usr/bin/env python3
"""
Final Validation Check Before Deployment

Runs a comprehensive check to ensure the optimized model is ready for production.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.repositories.games_repository import GamesRepository
from backend.database import get_db_connection
from model_training.adaptive_predictor import AdaptivePredictor
from model_training.calibration_metrics import expected_calibration_error
import pandas as pd

def check_dependencies():
    """Check that all required packages are installed."""
    print("Checking dependencies...")
    
    required = ['xgboost', 'scikit-learn', 'pandas', 'numpy']
    missing = []
    
    for pkg in required:
        try:
            __import__(pkg.replace('-', '_'))
            print(f"  ✅ {pkg}")
        except ImportError:
            print(f"  ❌ {pkg} - MISSING")
            missing.append(pkg)
    
    if missing:
        print(f"\n❌ Missing packages: {', '.join(missing)}")
        print("Install with: pip install " + ' '.join(missing))
        return False
    
    print("✅ All dependencies installed\n")
    return True


def check_model_initialization():
    """Check that model can initialize with optimized parameters."""
    print("Checking model initialization...")
    
    try:
        model = AdaptivePredictor(
            model_type='xgboost',
            xgb_learning_rate=0.05,
            xgb_max_depth=6,
            xgb_reg_alpha=0.1,
            xgb_reg_lambda=1.0,
            remove_useless_features=True,
        )
        print("✅ Model initialized successfully\n")
        return True
    except Exception as e:
        print(f"❌ Model initialization failed: {e}\n")
        return False


def check_training():
    """Check that model can train on recent data."""
    print("Checking model training...")
    
    try:
        db = get_db_connection()
        games_repo = GamesRepository(db)
        completed_games = games_repo.get_completed_games_df()
        
        # Use last 500 games for quick test
        recent = completed_games.tail(500).copy()
        
        model = AdaptivePredictor(
            model_type='xgboost',
            xgb_learning_rate=0.05,
            xgb_max_depth=6,
            xgb_reg_alpha=0.1,
            xgb_reg_lambda=1.0,
            remove_useless_features=True,
        )
        
        model.fit(recent, use_validation=False)
        
        print("✅ Model training successful")
        print(f"  Trained on {len(recent)} games\n")
        
        db.close()
        return True
    except Exception as e:
        print(f"❌ Model training failed: {e}\n")
        return False


def check_prediction():
    """Check that model can generate predictions."""
    print("Checking prediction generation...")
    
    try:
        db = get_db_connection()
        games_repo = GamesRepository(db)
        completed_games = games_repo.get_completed_games_df()
        
        # Train on older data, predict on recent
        older = completed_games.iloc[:1000].copy()
        recent = completed_games.iloc[1000:1100].copy()
        
        model = AdaptivePredictor(
            model_type='xgboost',
            xgb_learning_rate=0.05,
            xgb_max_depth=6,
            xgb_reg_alpha=0.1,
            xgb_reg_lambda=1.0,
            remove_useless_features=True,
        )
        
        model.fit(older, use_validation=False)
        predictions = model.predict(recent)
        
        print("✅ Predictions generated successfully")
        print(f"  Generated {len(predictions)} predictions")
        print(f"  Confidence range: {predictions['confidence'].min():.1%} - {predictions['confidence'].max():.1%}\n")
        
        db.close()
        return True
    except Exception as e:
        print(f"❌ Prediction generation failed: {e}\n")
        return False


def check_calibration():
    """Check that calibration metrics work."""
    print("Checking calibration metrics...")
    
    try:
        # Test with dummy data
        y_true = [1, 0, 1, 1, 0]
        y_pred = [0.8, 0.3, 0.9, 0.7, 0.4]
        
        ece = expected_calibration_error(y_true, y_pred)
        
        print("✅ Calibration metrics working")
        print(f"  Test ECE: {ece:.4f}\n")
        return True
    except Exception as e:
        print(f"❌ Calibration check failed: {e}\n")
        return False


def check_performance_benchmark():
    """Quick performance benchmark on recent data."""
    print("Running performance benchmark...")
    
    try:
        db = get_db_connection()
        games_repo = GamesRepository(db)
        completed_games = games_repo.get_completed_games_df()
        
        # Use last 1000 games, split 70/30
        recent = completed_games.tail(1000).copy()
        split_idx = int(len(recent) * 0.7)
        train = recent.iloc[:split_idx].copy()
        test = recent.iloc[split_idx:].copy()
        
        model = AdaptivePredictor(
            model_type='xgboost',
            xgb_learning_rate=0.05,
            xgb_max_depth=6,
            xgb_reg_alpha=0.1,
            xgb_reg_lambda=1.0,
            remove_useless_features=True,
        )
        
        model.fit(train, use_validation=False)
        predictions = model.predict(test)
        
        results = test.merge(predictions[['game_id', 'predicted_winner', 'confidence']], on='game_id')
        results['actual_winner'] = results.apply(
            lambda row: row['home_team'] if row['home_score'] > row['away_score'] else row['away_team'],
            axis=1
        )
        results['correct'] = (results['predicted_winner'] == results['actual_winner']).astype(int)
        
        overall_acc = results['correct'].mean()
        high_conf = results[results['confidence'] >= 0.80]
        high_acc = high_conf['correct'].mean() if len(high_conf) > 0 else 0
        
        print("✅ Performance benchmark complete")
        print(f"  Overall accuracy: {overall_acc:.1%}")
        print(f"  80%+ confidence: {len(high_conf)} games, {high_acc:.1%} accurate")
        
        # Check if performance meets minimum standards
        if high_acc >= 0.70:
            print("  ✅ Performance meets standards (80%+ picks ≥70% accurate)\n")
            db.close()
            return True
        else:
            print(f"  ⚠️  Performance below standards (80%+ picks: {high_acc:.1%} < 70%)\n")
            db.close()
            return False
            
    except Exception as e:
        print(f"❌ Performance benchmark failed: {e}\n")
        return False


def main():
    print("="*80)
    print("FINAL VALIDATION CHECK")
    print("="*80)
    print()
    
    checks = [
        ("Dependencies", check_dependencies),
        ("Model Initialization", check_model_initialization),
        ("Model Training", check_training),
        ("Prediction Generation", check_prediction),
        ("Calibration Metrics", check_calibration),
        ("Performance Benchmark", check_performance_benchmark),
    ]
    
    results = []
    for name, check_fn in checks:
        passed = check_fn()
        results.append((name, passed))
    
    # Summary
    print("="*80)
    print("VALIDATION SUMMARY")
    print("="*80)
    print()
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status:<10} {name}")
    
    print()
    
    all_passed = all(passed for _, passed in results)
    
    if all_passed:
        print("="*80)
        print("🎉 ALL CHECKS PASSED - READY FOR DEPLOYMENT!")
        print("="*80)
        print()
        print("Next steps:")
        print("1. Review docs/DEPLOYMENT_GUIDE.md")
        print("2. Merge prediction-logic-update branch to main")
        print("3. Deploy and monitor performance")
        print()
    else:
        print("="*80)
        print("⚠️  SOME CHECKS FAILED - NOT READY FOR DEPLOYMENT")
        print("="*80)
        print()
        print("Please fix the issues above before deploying.")
        print()
    
    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())
