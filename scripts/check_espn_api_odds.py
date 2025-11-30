import requests
import json
from datetime import datetime

def fetch_espn_scoreboard(date_str):
    """
    Fetch the ESPN API scoreboard JSON for a given date (YYYYMMDD).
    """
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard?dates={date_str}&groups=50"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()

def print_odds_for_games(date_str):
    data = fetch_espn_scoreboard(date_str)
    events = data.get('events', [])
    print(f"Found {len(events)} games for {date_str}")
    for event in events:
        game_id = event.get('id')
        competitions = event.get('competitions', [])
        if competitions:
            comp = competitions[0]
            odds = comp.get('odds', [])
            print(f"\nGame ID: {game_id}")
            print(f"Odds section: {json.dumps(odds, indent=2)}")
            if odds and isinstance(odds, list):
                moneyline = odds[0].get('moneyline')
                print(f"Moneyline field: {json.dumps(moneyline, indent=2)}")

if __name__ == "__main__":
    # Use today's date by default
    date_str = datetime.now().strftime("%Y%m%d")
    print_odds_for_games(date_str)
