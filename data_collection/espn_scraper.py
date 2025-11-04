"""
ESPN NCAA Basketball Game Scraper
This script scrapes current season game data directly from ESPN.
Use this to get live 2025-26 season data before it's available in ncaahoopR_data.
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import time
import json
import re
import os

class ESPNScraper:
    """Scraper for ESPN NCAA Basketball data."""
    
    def __init__(self):
        self.base_url = "https://www.espn.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
    
    def get_scoreboard(self, date):
        """
        Get ALL games for a specific date across all conferences.
        
        Args:
            date: Date in format YYYYMMDD or datetime object
            
        Returns:
            List of game dictionaries
        """
        if isinstance(date, datetime):
            date_str = date.strftime("%Y%m%d")
        else:
            date_str = str(date)
        
        all_games = []
        seen_game_ids = set()
        
        # ESPN uses group IDs for different conferences/divisions
        # Group 50 shows "All" games, but we'll also check individual groups
        # to ensure we get everything
        groups = ['50']  # Group 50 = "All Games"
        
        for group in groups:
            url = f"{self.base_url}/mens-college-basketball/scoreboard/_/seasontype/2/group/{group}/date/{date_str}"
            
            try:
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                
                # Parse games from this group
                games = self._parse_scoreboard_page(response.text, date_str)
                
                # Deduplicate by game_id
                for game in games:
                    game_id = game.get('game_id')
                    if game_id and game_id not in seen_game_ids:
                        seen_game_ids.add(game_id)
                        all_games.append(game)
                
            except Exception as e:
                print(f"Error fetching group {group} for {date_str}: {e}")
                continue
        
        return all_games
    
    def _parse_scoreboard_page(self, html, date_str):
        """Parse the scoreboard page HTML to extract game data from ESPN's __espnfitt__ data."""
        games = []
        
        try:
            # ESPN embeds game data in window['__espnfitt__']
            json_match = re.search(r'window\[\'__espnfitt__\'\]\s*=\s*(\{.+?\});', html, re.DOTALL)
            if not json_match:
                print(f"  Warning: Could not find __espnfitt__ data in page")
                return games
            
            data = json.loads(json_match.group(1))
            
            # Navigate to scoreboard events
            scoreboard = data.get('page', {}).get('content', {}).get('scoreboard', {})
            events = scoreboard.get('evts', [])
            
            if not events:
                print(f"  Warning: No events found in scoreboard data")
                return games
            
            print(f"  Found {len(events)} events in scoreboard data")
            
            # Parse each event
            for event in events:
                game_data = self._parse_event_json(event, date_str)
                if game_data:
                    games.append(game_data)
            
            return games
            
        except json.JSONDecodeError as e:
            print(f"  Error decoding JSON: {e}")
            return games
        except Exception as e:
            print(f"  Error parsing scoreboard: {e}")
            return games
    
    def _parse_event_json(self, event, date_str):
        """Parse a single event from ESPN's __espnfitt__ data structure."""
        try:
            game_id = str(event.get('id', ''))
            if not game_id:
                return None
            
            # Get competitors (index 0 = home, index 1 = away)
            competitors = event.get('competitors', [])
            if len(competitors) < 2:
                return None
            
            home_comp = competitors[0]
            away_comp = competitors[1]
            
            # Extract team info
            home_team = home_comp.get('displayName', home_comp.get('team', {}).get('displayName', ''))
            away_team = away_comp.get('displayName', away_comp.get('team', {}).get('displayName', ''))
            
            if not home_team or not away_team:
                return None
            
            # Extract scores
            home_score = int(home_comp.get('score', 0))
            away_score = int(away_comp.get('score', 0))
            
            # Extract rankings (ESPN uses 99 for unranked teams)
            home_rank = None
            away_rank = None
            
            home_rank_str = home_comp.get('rank')
            if home_rank_str:
                try:
                    rank_val = int(home_rank_str)
                    if rank_val != 99:  # 99 means unranked
                        home_rank = rank_val
                except:
                    pass
            
            away_rank_str = away_comp.get('rank')
            if away_rank_str:
                try:
                    rank_val = int(away_rank_str)
                    if rank_val != 99:  # 99 means unranked
                        away_rank = rank_val
                except:
                    pass
            
            # Determine game status
            completed = event.get('completed', False)
            status = event.get('status', {})
            status_type = status.get('type', {})
            status_state = status_type.get('state', 'pre')
            
            if completed or status_state == 'post':
                game_status = 'Final'
            elif status_state in ['in', 'halftime']:
                game_status = 'In Progress'
            else:
                game_status = 'Scheduled'
            
            # Build game URL
            game_url = f"https://www.espn.com/mens-college-basketball/game/_/gameId/{game_id}"
            
            # Format date for consistency
            formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            
            return {
                'game_id': game_id,
                'date': formatted_date,
                'game_day': formatted_date,
                'season': '2025-26',
                'away_team': away_team,
                'home_team': home_team,
                'away_score': away_score,
                'home_score': home_score,
                'away_rank': away_rank,
                'home_rank': home_rank,
                'game_status': game_status,
                'game_url': game_url,
                'is_neutral': 0,
                'home_record': '',
                'away_record': '',
                'home_point_spread': ''
            }
            
        except Exception as e:
            print(f"  Error parsing event: {e}")
            return None
    
    def _extract_from_json(self, data, date_str):
        """Extract game data from ESPN's JSON data."""
        games = []
        # This would parse ESPN's JSON structure if we found it
        # For now, return empty to use HTML fallback
        return games
    
    def _quick_parse_game(self, game_url, game_id, date_str):
        """Quickly parse a game from its URL."""
        try:
            response = self.session.get(game_url, timeout=5)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            game_data = {
                'game_id': game_id,
                'game_day': f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}",
                'season': '2025-26',
                'is_neutral': 0,
                'home_record': '',
                'away_record': '',
                'home_rank': None,
                'away_rank': None,
                'home_point_spread': ''
            }
            
            # Look for the Gamestrip module which has more reliable structure
            gamestrip = soup.find('div', class_='Gamestrip')
            if not gamestrip:
                gamestrip = soup  # Fallback to full page
            
            # Find team names - look for links to team pages
            team_links = gamestrip.find_all('a', class_='AnchorLink', href=re.compile(r'/mens-college-basketball/team/'))
            
            if len(team_links) >= 2:
                # Extract just the team name, avoiding duplicates
                away_text = team_links[0].get_text(strip=True)
                home_text = team_links[1].get_text(strip=True)
                
                # Remove rank numbers and clean up
                game_data['away_team'] = re.sub(r'^\d+\s*', '', away_text)
                game_data['home_team'] = re.sub(r'^\d+\s*', '', home_text)
                
                # Extract ranks if present
                away_rank = re.match(r'^(\d+)', away_text)
                if away_rank:
                    game_data['away_rank'] = int(away_rank.group(1))
                home_rank = re.match(r'^(\d+)', home_text)
                if home_rank:
                    game_data['home_rank'] = int(home_rank.group(1))
            else:
                # Fallback: try other methods
                return None
            
            # Find scores - look for ScoreCell divs
            score_divs = gamestrip.find_all('div', class_='Gamestrip__Score')
            if not score_divs:
                score_divs = soup.find_all('div', class_='ScoreCell__Score')
            
            # Get game status
            status_elem = soup.find('span', class_='ScoreCell__NetworkItem--time')
            if not status_elem:
                status_elem = soup.find('div', class_='ScoreboardScoreCell__Time')
            
            status_text = status_elem.get_text(strip=True).lower() if status_elem else ''
            
            # Determine if game is final
            if 'final' in status_text or 'f/' in status_text:
                game_data['game_status'] = 'Final'
                # Try to extract scores
                if len(score_divs) >= 2:
                    try:
                        score1 = score_divs[0].get_text(strip=True)
                        score2 = score_divs[1].get_text(strip=True)
                        score1_match = re.search(r'\d+', score1)
                        score2_match = re.search(r'\d+', score2)
                        if score1_match and score2_match:
                            game_data['away_score'] = int(score1_match.group())
                            game_data['home_score'] = int(score2_match.group())
                        else:
                            game_data['away_score'] = 0
                            game_data['home_score'] = 0
                    except:
                        game_data['away_score'] = 0
                        game_data['home_score'] = 0
                else:
                    game_data['away_score'] = 0
                    game_data['home_score'] = 0
            else:
                game_data['game_status'] = 'Scheduled'
                game_data['away_score'] = 0
                game_data['home_score'] = 0
            
            # Check for neutral site
            location = soup.find('div', class_='Gamestrip__Location')
            if location and 'neutral' in location.get_text().lower():
                game_data['is_neutral'] = 1
            
            return game_data
            
        except Exception as e:
            print(f"Error parsing game {game_id}: {e}")
            return None
    
    def _extract_game_data(self, game_div, date_str):
        """Extract game data from a game container."""
        game_data = {}
        
        # Try to find game ID from links
        game_links = game_div.find_all('a', href=True)
        game_id = None
        for link in game_links:
            if '/game/' in link['href']:
                match = re.search(r'/game/(\d+)', link['href'])
                if match:
                    game_id = match.group(1)
                    break
        
        if not game_id:
            return None
        
        game_data['game_id'] = game_id
        game_data['game_day'] = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        
        # Find team names and scores
        teams = game_div.find_all('div', class_='ScoreCell__TeamName')
        scores = game_div.find_all('div', class_='ScoreCell__Score')
        
        if len(teams) >= 2:
            # Determine home/away (typically away is first, home is second)
            game_data['away_team'] = teams[0].get_text(strip=True)
            game_data['home_team'] = teams[1].get_text(strip=True)
            
            # Get scores if available
            if len(scores) >= 2:
                try:
                    game_data['away_score'] = int(scores[0].get_text(strip=True))
                    game_data['home_score'] = int(scores[1].get_text(strip=True))
                    game_data['game_status'] = 'Final'
                except (ValueError, AttributeError):
                    game_data['away_score'] = 0
                    game_data['home_score'] = 0
                    game_data['game_status'] = 'Scheduled'
            else:
                game_data['away_score'] = 0
                game_data['home_score'] = 0
                game_data['game_status'] = 'Scheduled'
        
        # Check for neutral site
        location_text = game_div.get_text().lower()
        game_data['is_neutral'] = 1 if 'neutral' in location_text else 0
        
        # Initialize other fields
        game_data['home_record'] = ''
        game_data['away_record'] = ''
        game_data['home_rank'] = None
        game_data['away_rank'] = None
        game_data['home_point_spread'] = ''
        game_data['season'] = '2025-26'
        
        return game_data if game_data.get('home_team') and game_data.get('away_team') else None
    
    def get_game_detail(self, game_id):
        """
        Get detailed game information including box score.
        
        Args:
            game_id: ESPN game ID
            
        Returns:
            Dictionary with game details
        """
        url = f"{self.base_url}/mens-college-basketball/game/_/gameId/{game_id}"
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract additional details
            game_details = {}
            
            # Try to get records
            records = soup.find_all('div', class_='record')
            if len(records) >= 2:
                game_details['away_record'] = records[0].get_text(strip=True)
                game_details['home_record'] = records[1].get_text(strip=True)
            
            # Try to get rankings
            ranks = soup.find_all('span', class_='rank')
            if ranks:
                for i, rank in enumerate(ranks[:2]):
                    rank_text = rank.get_text(strip=True).replace('#', '')
                    if i == 0:
                        game_details['away_rank'] = int(rank_text) if rank_text.isdigit() else None
                    else:
                        game_details['home_rank'] = int(rank_text) if rank_text.isdigit() else None
            
            return game_details
            
        except Exception as e:
            print(f"Error fetching game {game_id} details: {e}")
            return {}
    
    def get_season_games(self, start_date, end_date=None):
        """
        Get all games between start_date and end_date.
        
        Args:
            start_date: Start date (datetime or YYYYMMDD)
            end_date: End date (datetime or YYYYMMDD), defaults to today
            
        Returns:
            DataFrame with all games
        """
        if end_date is None:
            end_date = datetime.now()
        
        if isinstance(start_date, str):
            # Try both date formats
            try:
                start_date = datetime.strptime(start_date, "%Y%m%d")
            except ValueError:
                start_date = datetime.strptime(start_date, "%Y-%m-%d")
        if isinstance(end_date, str):
            # Try both date formats
            try:
                end_date = datetime.strptime(end_date, "%Y%m%d")
            except ValueError:
                end_date = datetime.strptime(end_date, "%Y-%m-%d")
        
        all_games = []
        current_date = start_date
        
        print(f"Scraping ESPN games from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        print("This may take several minutes...")
        
        while current_date <= end_date:
            print(f"  Fetching games for {current_date.strftime('%Y-%m-%d')}...", end='')
            
            games = self.get_scoreboard(current_date)
            if games:
                all_games.extend(games)
                print(f" Found {len(games)} games")
            else:
                print(" No games")
            
            current_date += timedelta(days=1)
            time.sleep(0.5)  # Be respectful to ESPN servers
        
        if not all_games:
            print("\nNo games found in date range!")
            return pd.DataFrame()
        
        print(f"\nTotal games scraped: {len(all_games)}")
        
        # Convert to DataFrame
        df = pd.DataFrame(all_games)
        
        # Deduplicate by game_id
        df = df.drop_duplicates(subset=['game_id'], keep='first')
        
        print(f"Unique games after deduplication: {len(df)}")
        
        return df
    
    def enrich_games_with_details(self, games_df):
        """
        Fetch additional details for each game (records, rankings).
        
        Args:
            games_df: DataFrame of games
            
        Returns:
            Enhanced DataFrame
        """
        print(f"\nEnriching {len(games_df)} games with additional details...")
        
        for idx, row in games_df.iterrows():
            if idx % 50 == 0 and idx > 0:
                print(f"  Processed {idx}/{len(games_df)} games...")
            
            details = self.get_game_detail(row['game_id'])
            
            if details:
                for key, value in details.items():
                    games_df.at[idx, key] = value
            
            time.sleep(0.3)  # Be respectful
        
        print("Enrichment complete!")
        return games_df


def main():
    """Main function to scrape current season games."""
    print("="*80)
    print("ESPN NCAA BASKETBALL SCRAPER")
    print("="*80)
    print("Fetching 2025-26 season games from ESPN...")
    print()
    
    # Initialize scraper
    scraper = ESPNScraper()
    
    # Define season start (typical NCAA season starts early November)
    season_start = datetime(2025, 11, 1)
    today = datetime.now()
    
    # Get all games from season start to today
    games_df = scraper.get_season_games(season_start, today)
    
    if games_df.empty:
        print("\nNo games found. The 2025-26 season may not have started yet.")
        print("Check ESPN manually: https://www.espn.com/mens-college-basketball/scoreboard")
        return
    
    # Optional: Enrich with details (this is slow, so make it optional)
    print("\nWould you like to fetch additional details (records, rankings)?")
    print("This will take longer but provides more complete data.")
    enrich = input("Enrich data? (y/n): ").lower().strip() == 'y'
    
    if enrich:
        games_df = scraper.enrich_games_with_details(games_df)
    
    # Save to data directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(os.path.dirname(script_dir), 'data')
    os.makedirs(data_dir, exist_ok=True)
    
    output_path = os.path.join(data_dir, 'ESPN_Current_Season.csv')
    games_df.to_csv(output_path, index=False)
    
    print(f"\n{'='*80}")
    print("SCRAPING COMPLETE!")
    print(f"{'='*80}")
    print(f"Saved {len(games_df)} games to: {output_path}")
    
    # Summary
    completed = len(games_df[games_df['game_status'] == 'Final'])
    upcoming = len(games_df[games_df['game_status'] == 'Scheduled'])
    
    print(f"\nSummary:")
    print(f"  Completed games: {completed}")
    print(f"  Upcoming games: {upcoming}")
    print(f"  Date range: {games_df['game_day'].min()} to {games_df['game_day'].max()}")
    
    print(f"\nSample of data:")
    print(games_df.head())


if __name__ == "__main__":
    main()
