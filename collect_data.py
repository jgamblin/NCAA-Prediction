#!/usr/bin/env python3
"""
NCAA Basketball Data Collection Pipeline
Run this script to collect game data for multiple seasons.
"""

import sys
import os

# Add data_collection to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'data_collection'))

# Import and run
from all_games import main

if __name__ == "__main__":
    main()
