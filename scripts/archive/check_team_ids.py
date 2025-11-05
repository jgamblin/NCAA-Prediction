#!/usr/bin/env python3
"""
Archived: Original exploratory script for extracting ESPN team IDs (moved from repo root).
Functionality now integrated into data_collection/espn_scraper.py.
"""

import requests
import json
import re

game_id = "401827172"
url = f"https://www.espn.com/mens-college-basketball/game/_/gameId/{game_id}"
print("Checking ESPN page for team IDs:", url)
response = requests.get(url, headers={
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
})
html = response.text
json_match = re.search(r"window\['__espnfitt__'\]\s*=\s*(\{.+?\});", html, re.DOTALL)
if not json_match:
    print("No __espnfitt__ data found.")
    raise SystemExit(1)

print("Found embedded JSON blob; parsing...")
data = json.loads(json_match.group(1))
page = data.get('page', {})
content = page.get('content', {})
scoreboard = content.get('headerscoreboard', {})
competitors = scoreboard.get('ctts', []) or scoreboard.get('competitors', [])
for i, comp in enumerate(competitors):
    role = 'Home' if i == 0 else 'Away'
    tid = comp.get('id') or comp.get('team', {}).get('id')
    name = comp.get('displayName') or comp.get('nm')
    print(f"{role}: id={tid} name={name}")
print("Done. Use these IDs in espn_scraper for stable identity.")
