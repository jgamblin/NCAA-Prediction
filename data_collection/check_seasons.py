#!/usr/bin/env python3
"""
Quick utility to check what seasons are available in ncaahoopR_data repository.
"""

import requests

def get_available_seasons():
    """Get list of available seasons from ncaahoopR_data repository."""
    api_url = "https://api.github.com/repos/lbenz730/ncaahoopR_data/contents/"
    
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        files = response.json()
        # Get directories that look like seasons (YYYY-YY format)
        seasons = [f['name'] for f in files if f['type'] == 'dir' and '-' in f['name'] and f['name'][0].isdigit()]
        return sorted(seasons)
    except Exception as e:
        print(f"Error fetching available seasons: {e}")
        return []


if __name__ == "__main__":
    print("Checking available seasons in ncaahoopR_data repository...")
    print("Repository: https://github.com/lbenz730/ncaahoopR_data\n")
    
    seasons = get_available_seasons()
    
    if seasons:
        print(f"Found {len(seasons)} available seasons:\n")
        for season in seasons:
            print(f"  - {season}")
        print(f"\nMost recent season: {seasons[-1]}")
        print(f"\nTo use a specific season, update the SEASON variable in all_games.py")
        print(f"or run: python3 all_games.py <season>")
    else:
        print("Could not retrieve season list.")
