#!/usr/bin/env python3
"""
Team name normalization utilities for NCAA basketball predictions.

Handles inconsistencies in team naming between historical data
and current ESPN scraping (e.g., "Indiana" vs "Indiana Hoosiers").
"""

import re
import os
import json


# Common mascot suffixes to remove for normalization
# Note: Multi-word mascots are sorted longest-first at runtime to avoid partial matches
MASCOTS = [
    'Aggies', 'Ambassadors', 'Anteaters', 'Aztecs',
    'Badgers', 'Bearcats', 'Bears', 'Beavers', 'Billikens', 'Bison', 'Blackbirds',
    'Blue Devils', 'Blue Hose', 'Blue Jays', 'Blue Raiders', 'Bluejays', 'Bobcats',
    'Boilermakers', 'Bonnies', 'Braves', 'Broncos', 'Broncs', 'Bruins', 'Buckeyes', 
    'Buffaloes', 'Bulldogs', 'Bulls',
    'Camels', 'Cardinals', 'Catamounts', 'Cavaliers', 'Chanticleers', 'Chippewas',
    'Colonials', 'Commodores', 'Cougars', 'Cowboys', 'Coyotes', 'Crimson', 'Crusaders',
    'Cyclones',
    'Delta Devils', 'Demons', 'Demon Deacons', 'Devils', 'Dolphins', 'Dragons', 'Dukes',
    'Eagles', 'Explorers',
    'Falcons', 'Fighting Irish', 'Flames', 'Flyers', 'Friars', 'Blazers', 'Keydets',
    'Gauchos', 'Gaels', 'Gators', 'Generals', 'Gentlemen', 'Golden Eagles',
    'Golden Gophers', 'Golden Grizzlies', 'Gophers', 'Greyhounds', 'Grizzlies',
    'Hatters', 'Hawkeyes', 'Hawks', 'Highlanders', 'Hilltoppers', 'Hokies',
    'Hoosiers', 'Hornets', 'Huskies',
    'Illini', 'Indians',
    'Jacks', 'Jaguars', 'Jaspers', 'Jayhawks',
    'Knights',
    'Lakers', 'Lancers', 'Leathernecks', 'Leopards', 'Lions', 'Lobos', 'Lumberjacks',
    'Lutes',
    'Mastodons', 'Matadors', 'Mavericks', 'Mean Green', 'Midshipmen', 'Miners',
    'Minutemen', 'Monarchs', 'Mountaineers', 'Musketeers', 'Mustangs',
    'Nanooks', 'Nittany Lions',
    'Orangemen', 'Orediggers', 'Owls',
    'Paladins', 'Panthers', 'Patriots', 'Peacocks', 'Penguins', 'Phoenix',
    'Pilots', 'Pirates', 'Privateers',
    'Quakers',
    'Racers', 'Raiders', 'Rams', 'Ramblers', "Ramblin' Rams", "Ramblin' Wreck",
    'Ravens', 'Razorbacks', 'Rebels', 'Red', 'Red Dragons', 'Red Flash', 'Red Raiders',
    'Red Storm', 'Red Wolves', 'Redbirds', 'Redhawks', 'Retrievers', 'Roadrunners',
    'Rockets', 'Royals',
    'Salukis', 'Scarlet Knights', 'Screaming Eagles', 'Seawolves', 'Seminoles',
    'Shockers', 'Sooners', 'Spartans', 'Spiders', 'Spirit', 'Stags', 'Sun Devils',
    'Sycamores',
    'Tar Heels', 'Terrapins', 'Terriers', 'Texans', 'Thundering Herd', 'Tigers', 'Titans',
    'Trailblazers', 'Tribe', 'Trojans', 'Turkeys',
    'Utes',
    'Vandals', 'Vikings', 'Volunteers',
    'Warriors', 'Waves', 'Wildcats', 'Wolfpack', 'Wolves', 'Wolverines',
    'Yellow Jackets', 'Zips'
]

# Special cases where simple suffix removal doesn't work
SPECIAL_CASES = {
    # Current name -> Normalized name
    'Saint Mary\'s Gaels': 'Saint Mary\'s',
    'St. Mary\'s Gaels': 'St. Mary\'s',
    'Saint Joseph\'s Hawks': 'Saint Joseph\'s',
    'St. Joseph\'s Hawks': 'St. Joseph\'s',
    'Saint Peter\'s Peacocks': 'Saint Peter\'s',
    'St. Peter\'s Peacocks': 'St. Peter\'s',
    'Saint John\'s Red Storm': 'St. John\'s',
    'St. John\'s Red Storm': 'St. John\'s',
    'Saint Louis Billikens': 'Saint Louis',
    'St. Louis Billikens': 'Saint Louis',
    'Saint Bonaventure Bonnies': 'St. Bonaventure',
    'St. Bonaventure Bonnies': 'St. Bonaventure',
    'Stephen F. Austin Lumberjacks': 'Stephen F. Austin',
    'SFA Lumberjacks': 'Stephen F. Austin',
    'UT San Antonio Roadrunners': 'UTSA',
    'Texas-San Antonio Roadrunners': 'UTSA',
    'University of Texas San Antonio Roadrunners': 'UTSA',
    'Miami (FL) Hurricanes': 'Miami (FL)',
    'Miami (Ohio) RedHawks': 'Miami (OH)',
    'Miami OH RedHawks': 'Miami (OH)',
    'Texas A&M-Corpus Christi Islanders': 'Texas A&M-Corpus Christi',
    'Louisiana State Tigers': 'LSU',
    'Louisiana State University Tigers': 'LSU',
    'University of Central Florida Knights': 'UCF',
    'Central Florida Knights': 'UCF',
    'University of Connecticut Huskies': 'Connecticut',
    'Southern Methodist Mustangs': 'SMU',
    'Texas Christian Horned Frogs': 'TCU',
    'Brigham Young Cougars': 'BYU',
    'Virginia Commonwealth Rams': 'VCU',
    'University of Southern California Trojans': 'USC',
    'Southern California Trojans': 'USC',
    # App State variations - ESPN changed from abbreviation to full name
    'App State': 'Appalachian St',
    'App State Mountaineers': 'Appalachian St',
    'Appalachian State': 'Appalachian St',
    # Ottawa variations
    'Ottawa (AZ)': 'Ottawa University Arizona',
    'Ottawa (AZ) Spirit': 'Ottawa University Arizona',
    # Dickinson - note this is NOT Fairleigh Dickinson
    'Dickinson (PA)': 'Dickinson (PA)',
    'Dickinson (PA) Red': 'Dickinson (PA)',
    'Dickinson (PA) Red Devils': 'Dickinson (PA)',
    # Maryland Eastern Shore - hyphen vs space variations
    'Maryland Eastern Shore': 'Maryland-Eastern Shore',
    'Maryland Eastern Shore Hawks': 'Maryland-Eastern Shore',
    # Bethesda variations - with/without University
    'Bethesda University': 'Bethesda',
    'Bethesda University Flames': 'Bethesda',
    # Tarleton variations - with/without State
    'Tarleton State': 'Tarleton',
    'Tarleton State Texans': 'Tarleton',
    # James Madison - commonly abbreviated as JMU
    'JMU': 'James Madison',
    'JMU Dukes': 'James Madison',
    # North Dakota State - abbreviated name variations
    'North Dakota St': 'North Dakota State',
    'North Dakota St Bison': 'North Dakota State',
    'NDSU': 'North Dakota State',
    # Utah Tech - formerly Dixie State (school name change)
    'Dixie State': 'Utah Tech',
    'Dixie State Trailblazers': 'Utah Tech',
    # Mississippi State variations
    'Miss St': 'Mississippi State',
    'Miss State': 'Mississippi State',
    # Loyola schools - need to disambiguate
    'Loyola-Chicago': 'Loyola Chicago',
    'Loyola Chicago Ramblers': 'Loyola Chicago',
    'Loyola (MD)': 'Loyola Maryland',
    'Loyola MD': 'Loyola Maryland',
    'Loyola Maryland Greyhounds': 'Loyola Maryland',
    'Loyola Mary': 'Loyola Marymount',  # Truncated name in data
    'Loyola Marymount Lions': 'Loyola Marymount',
    # Middle Tennessee variations
    'Mid Tennessee': 'Middle Tennessee',
    'Middle Tennessee State': 'Middle Tennessee',
    'MTSU': 'Middle Tennessee',
        # Miami - need to distinguish FL from OH
        'Miami': 'Miami (FL)',  # Default Miami to Florida (major program)
        'Miami Hurricanes': 'Miami (FL)',
        # Connecticut variations
        'UConn': 'Connecticut',
        'UConn Huskies': 'Connecticut',
        # LMU - Loyola Marymount (WCC school)
        'LMU': 'Loyola Marymount',
        'LMU Lions': 'Loyola Marymount',
    # California Golden Bears variations
    'California Golden Bears': 'California',
    'Cal Golden Bears': 'California',
    'Cal Bears': 'California',
    # Exact short form 'Cal' (ensure not Cal Poly etc.)
    'Cal': 'California',
    # Florida Atlantic variations
    'FAU': 'Florida Atlantic',
    'Florida Atlantic Owls': 'Florida Atlantic',
    # East Carolina variations (avoid mapping unrelated Carolina schools despite partial matches)
    'ECU': 'East Carolina',
    'East Carolina Pirates': 'East Carolina',
    # Louisiana Tech variations
    'LA Tech': 'Louisiana Tech',
    'Louisiana Tech Bulldogs': 'Louisiana Tech',
    # Florida International variations
    'FIU': 'Florida International',
    'Florida International Panthers': 'Florida International',
    'Florida Intl': 'Florida International',
    # Jacksonville State variations
    'Jacksonville St': 'Jacksonville State',
    'Jacksonville State Gamecocks': 'Jacksonville State',
    'Jax State': 'Jacksonville State',
    # Sam Houston State variations
    'Sam Houston': 'Sam Houston State',
    'Sam Houston St': 'Sam Houston State',
    'Sam Houston Bearkats': 'Sam Houston State',
    'Sam Houston State Bearkats': 'Sam Houston State',
    # San Jose State variations
    'San Jose St': 'San Jose State',
    'San José State': 'San Jose State',
    'San José State Spartans': 'San Jose State',
    'San Jose State Spartans': 'San Jose State',
    # Mojibake (mis-encoded) San Jose State variants
    'San JosÃ© State': 'San Jose State',
    'San JosÃ© State Spartans': 'San Jose State',
    'SJSU': 'San Jose State',
    'SJSU Spartans': 'San Jose State',
    # Massachusetts variations
    'UMass': 'Massachusetts',
    'Massachusetts Minutemen': 'Massachusetts',
    'Massachusetts-Boston': 'Massachusetts',
    'Massachusetts College': 'Massachusetts',
    # George Washington variations (old nickname Colonials replaced by Revolutionaries)
    'G Washington': 'George Washington',
    'George Washington Colonials': 'George Washington',
    'George Washington Revolutionaries': 'George Washington',
    'George Wash': 'George Washington',
    # New Mexico State variations
    'New Mexico St': 'New Mexico State',
    'NMSU': 'New Mexico State',
    'New Mexico State Aggies': 'New Mexico State',
    # Missing D1 coverage alias additions
    'AR-Pine Bluff': 'Arkansas-Pine Bluff',
    'Arkansas-Pine Bluff Golden': 'Arkansas-Pine Bluff',
    'Arkansas Pine Bluff': 'Arkansas-Pine Bluff',
    'Nicholls': 'Nicholls State',
    'Nicholls Colonels': 'Nicholls State',
    'SE Louisiana': 'Southeastern Louisiana',
    'Southeast Louisiana': 'Southeastern Louisiana',
    'Grambling': 'Grambling State',
    'Grambling State Tigers': 'Grambling State',
    'LIU': 'Long Island',
    'LIU Sharks': 'Long Island',
    'Saint Francis (PA)': 'St. Francis (PA)',
    'Saint Francis PA': 'St. Francis (PA)',
    'St Francis (PA)': 'St. Francis (PA)',
    'Saint Thomas (MN)': 'St. Thomas (MN)',
    'St Thomas (MN)': 'St. Thomas (MN)',
    'St Thomas MN': 'St. Thomas (MN)',
    'BYU': 'Brigham Young',
    'SMU': 'Southern Methodist',
    'TCU': 'Texas Christian',
    'VCU': 'Virginia Commonwealth',
    'The Citadel': 'Citadel',
    # Additional low-game truncated/abbreviated forms
    'Abil Christian': 'Abilene Christian',
    'Charleston So': 'Charleston Southern',
    'E Washington': 'Eastern Washington',
    'C. Carolina': 'Coastal Carolina',
    'E Illinois': 'Eastern Illinois',
    'Cent Arkansas': 'Central Arkansas',
    'Cent Michigan': 'Central Michigan',
    'Fair Dickinson': 'Fairleigh Dickinson',
    'Fort Wayne': 'Purdue Fort Wayne',
    'E Kentucky': 'Eastern Kentucky',
    'Ga Southern': 'Georgia Southern',
    'E Michigan': 'Eastern Michigan',
    'FGCU': 'Florida Gulf Coast',
    # Texas A&M-Corpus Christi additional variants
    'Texas A&M-CC': 'Texas A&M-Corpus Christi',
    'TAMU-CC': 'Texas A&M-Corpus Christi',
    'A&M-CC': 'Texas A&M-Corpus Christi',
    'Texas A&M Corpus Christi': 'Texas A&M-Corpus Christi',
    'Texas A&M Corpus Christi Islanders': 'Texas A&M-Corpus Christi',
    # Seattle variants
    'Seattle U': 'Seattle',
    'Seattle University': 'Seattle',
    # Explicit hybrid guards (prevent impossible cross-mascot collapses)
    'Penn State Quakers': 'Penn State Quakers',  # Should not normalize across institutions
    'Penn Nittany Lions': 'Penn Nittany Lions',  # Guard against accidental mascot stripping
    # East Tennessee State variants (ETSU)
    'ETSU': 'East Tennessee State',
    'ETSU Buccaneers': 'East Tennessee State',
    'E Tenn State': 'East Tennessee State',
    'E Tennessee State': 'East Tennessee State',
    'East Tenn State': 'East Tennessee State',
    'East Tenn St': 'East Tennessee State',
    'East Tennessee St': 'East Tennessee State',
    'East Tennessee State Buccaneers': 'East Tennessee State',
}


def normalize_team_name(team_name):
    """
    Normalize team name by removing mascot suffixes and fixing URL encoding.
    
    Handles multiple inconsistencies:
    - Historical data: "Indiana" vs current "Indiana Hoosiers"
    - URL encoding: "Alabama A%26M" vs "Alabama A&M"
    - Case variations and extra spaces
    
    Args:
        team_name: Raw team name from data source
        
    Returns:
        Normalized team name without mascot suffix
        
    Examples:
        >>> normalize_team_name("Indiana Hoosiers")
        'Indiana'
        >>> normalize_team_name("Alabama A&M Bulldogs")
        'Alabama A&M'
        >>> normalize_team_name("Alabama A%26M")
        'Alabama A&M'
        >>> normalize_team_name("St. John's Red Storm")
        "St. John's"
    """
    if not team_name or not isinstance(team_name, str):
        return team_name
    
    # Step 1: URL decode (fix %26 -> &, %20 -> space, etc.)
    import urllib.parse
    team_name = urllib.parse.unquote(team_name)

    # Step 1.5: Repair common mojibake (UTF-8 decoded as Latin-1) e.g. 'San JosÃ©'
    # If the string contains the mojibake marker 'Ã', attempt a round-trip re-encoding
    if 'Ã' in team_name:
        try:
            repaired = team_name.encode('latin-1').decode('utf-8')
            team_name = repaired
        except UnicodeError:
            # If repair fails, keep original
            pass
    
    # Step 2: Strip extra whitespace
    team_name = team_name.strip()
    
    # Step 3: ESPN alias map (if available)
    # Load lazily once
    global ESPN_ALIASES
    if 'ESPN_ALIASES' not in globals():
        ESPN_ALIASES = {}
        try:
            alias_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'espn_alias_map.json')
            if os.path.exists(alias_path):
                with open(alias_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    ESPN_ALIASES = data.get('alias_to_canonical', {}) or {}
        except Exception:
            ESPN_ALIASES = {}

    if team_name in ESPN_ALIASES:
        team_name = ESPN_ALIASES[team_name]

    # Step 4: Check special cases
    if team_name in SPECIAL_CASES:
        return SPECIAL_CASES[team_name]
    
    # Step 5: Try removing mascot suffixes
    # Sort mascots by length (longest first) to match multi-word mascots before single-word
    sorted_mascots = sorted(MASCOTS, key=len, reverse=True)
    
    original = team_name
    for mascot in sorted_mascots:
        # Match mascot at end of string (with optional 's' for plural variations)
        pattern = rf'\s+{re.escape(mascot)}s?$'
        if re.search(pattern, team_name, re.IGNORECASE):
            normalized = re.sub(pattern, '', team_name, flags=re.IGNORECASE)
            # Only return if we actually removed something and have text left
            if normalized and normalized != team_name:
                return normalized.strip()
    
    # If no mascot found, return original
    return original


def normalize_game_dataframe(df, team_columns=['home_team', 'away_team']):
    """
    Normalize team names in a DataFrame.
    
    Args:
        df: pandas DataFrame with team name columns
        team_columns: List of column names to normalize
        
    Returns:
        DataFrame with normalized team names
    """
    df = df.copy()
    for col in team_columns:
        if col in df.columns:
            df[col] = df[col].apply(normalize_team_name)
    return df


def test_normalization():
    """Test normalization with known cases."""
    test_cases = [
        ("Indiana Hoosiers", "Indiana"),
        ("Alabama A&M Bulldogs", "Alabama A&M"),
        ("Alabama A%26M", "Alabama A&M"),  # URL encoded ampersand
        ("Alabama A%26M Bulldogs", "Alabama A&M"),  # URL encoded + mascot
        ("Duke Blue Devils", "Duke"),
        ("North Carolina Tar Heels", "North Carolina"),
        ("Michigan Wolverines", "Michigan"),
        ("Kansas Jayhawks", "Kansas"),
        ("UCLA Bruins", "UCLA"),
        ("Kentucky Wildcats", "Kentucky"),
        ("Gonzaga Bulldogs", "Gonzaga"),
        ("Villanova Wildcats", "Villanova"),
        ("St. John's Red Storm", "St. John's"),
        ("VCU Rams", "VCU"),
        ("LSU Tigers", "LSU"),
        # URL encoded cases
        ("Texas%20A%26M%20Aggies", "Texas A&M"),  # Space and ampersand encoded
        ("Texas A%26M Aggies", "Texas A&M"),
        # Multi-word mascot cases (must match longest first)
        ("Marquette Golden Eagles", "Marquette"),
        ("Oral Roberts Golden Eagles", "Oral Roberts"),
        ("Mississippi Valley State Delta Devils", "Mississippi Valley State"),
        ("Rutgers Scarlet Knights", "Rutgers"),
        ("La Salle Explorers", "La Salle"),
        ("New Mexico Lobos", "New Mexico"),
        ("RIT Tigers", "RIT"),
        ("Rider Broncs", "Rider"),
        ("South Dakota Coyotes", "South Dakota"),
        ("Tarleton State Texans", "Tarleton"),  # Maps to historical "Tarleton"
        # Abbreviation/alternate name cases
        ("App State", "Appalachian St"),
        ("App State Mountaineers", "Appalachian St"),
        ("Appalachian State", "Appalachian St"),
        ("Appalachian St", "Appalachian St"),
        ("Ottawa (AZ) Spirit", "Ottawa University Arizona"),
        ("Ottawa University Arizona", "Ottawa University Arizona"),
        ("Pacific Lutheran Lutes", "Pacific Lutheran"),
        ("Pacific Lutheran", "Pacific Lutheran"),
        ("Dickinson (PA) Red Devils", "Dickinson (PA)"),
        ("College Of Biblical Studies Ambassadors", "College Of Biblical Studies"),
        # San Jose State encoding/alias variants
        ("San José State Spartans", "San Jose State"),
        ("San JosÃ© State Spartans", "San Jose State"),  # mojibake variant should repair
        ("San JosÃ© State", "San Jose State"),
        ("San José State", "San Jose State"),
        # Should not change (no mascot)
        ("Indiana", "Indiana"),
        ("Alabama A&M", "Alabama A&M"),
        ("Duke", "Duke"),
    ]
    
    print("Testing team name normalization:")
    print("="*70)
    all_passed = True
    
    for input_name, expected in test_cases:
        result = normalize_team_name(input_name)
        status = "✓" if result == expected else "✗"
        if result != expected:
            all_passed = False
            print(f"{status} '{input_name}' -> '{result}' (expected '{expected}')")
        else:
            print(f"{status} '{input_name}' -> '{result}'")
    
    print("="*70)
    if all_passed:
        print("All tests passed! ✓")
    else:
        print("Some tests failed! ✗")
    
    return all_passed


if __name__ == "__main__":
    test_normalization()
