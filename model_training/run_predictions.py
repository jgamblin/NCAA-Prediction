#!/usr/bin/env python3
"""
NCAA Basketball Prediction Pipeline
Run this script to train models and make predictions on upcoming games.
"""

import sys
import os

# Add model_training to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'model_training'))

# Import and run
from ncaa_predictions_v2 import main

if __name__ == "__main__":
    main()
