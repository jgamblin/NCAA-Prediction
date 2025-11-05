#!/usr/bin/env python3
"""Build ESPN alias map for men's college basketball teams.

Fetches ESPN teams endpoint and constructs a mapping of all discovered aliases
(displayName, shortDisplayName, abbreviation, location+nickname, name+nickname) to a canonical
normalized team name (mascot stripped using normalize_team_name).

Outputs JSON: data/espn_alias_map.json with structure:
{
  "generated_at": ISO_DATE,
  "team_count": N,
  "alias_to_canonical": { alias: canonical, ... },
  "teams": [ {"espn_id": id, "displayName": ..., "canonical": ... , "aliases": [...] }, ... ]
}
"""
import os
import json
import requests
from datetime import datetime
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, 'data')
os.makedirs(DATA_DIR, exist_ok=True)
OUTPUT_PATH = os.path.join(DATA_DIR, 'espn_alias_map.json')

sys.path.insert(0, ROOT)
from data_collection.team_name_utils import normalize_team_name

API_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams"

def fetch_espn_teams():
    resp = requests.get(API_URL, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    leagues = data.get('sports', [{}])[0].get('leagues', [])
    if not leagues:
        return []
    teams = []
    for lg in leagues:
        for t in lg.get('teams', []):
            team_obj = t.get('team', {})
            if not team_obj:
                continue
            teams.append(team_obj)
    return teams

def build_alias_map(raw_teams):
    alias_to_canonical = {}
    team_records = []
    for t in raw_teams:
        display = t.get('displayName') or t.get('name') or ''
        short = t.get('shortDisplayName') or ''
        abbr = t.get('abbreviation') or ''
        nickname = t.get('nickname') or ''
        location = t.get('location') or ''
        espn_id = t.get('id')

        # Construct potential raw aliases
        potential_aliases = set()
        for val in [display, short, abbr, nickname, location, f"{location} {nickname}".strip(), f"{display} {nickname}".strip()]:
            if val and len(val) > 1:
                potential_aliases.add(val)

        # Normalize canonical name (strip mascot, fix encoding)
        canonical = normalize_team_name(display)

        # Map each alias to canonical (un-normalized alias key to canonical normalized)
        for alias in potential_aliases:
            # Avoid overwriting if alias already mapped to same canonical; if conflicting, keep first
            if alias not in alias_to_canonical:
                alias_to_canonical[alias] = canonical

        team_records.append({
            'espn_id': espn_id,
            'displayName': display,
            'shortDisplayName': short,
            'abbreviation': abbr,
            'nickname': nickname,
            'location': location,
            'canonical': canonical,
            'aliases': sorted(potential_aliases),
        })

    return alias_to_canonical, team_records

def main():
    try:
        raw_teams = fetch_espn_teams()
    except Exception as e:
        print(f"Error fetching ESPN teams: {e}")
        sys.exit(1)

    alias_map, team_records = build_alias_map(raw_teams)

    payload = {
        'generated_at': datetime.utcnow().isoformat(),
        'team_count': len(team_records),
        'alias_to_canonical': alias_map,
        'teams': team_records,
        'source': API_URL,
    }

    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"ESPN alias map written to {OUTPUT_PATH} with {len(alias_map)} aliases for {len(team_records)} teams.")

if __name__ == '__main__':
    main()
