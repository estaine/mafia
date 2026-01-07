#!/usr/bin/env python3
"""
Sync engine for Mafia game data import from Google Sheets to Supabase.
Provides reusable functions that return structured statistics instead of printing.
"""

import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://mpasyybxqvzbnxciejqo.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID', '1FJ9T5Zgh5_yS_G-Dx_FAP12RRXsH3IG45WCoZUcaHgA')
SHEET_GID = os.getenv('SHEET_GID', '216801262')

# Role code mapping
ROLE_CODES = {
    'M': 'M',      # Мірны жыхар (Citizen)
    'Sh': 'Sh',    # Шэрыф (Sheriff)
    'Mf': 'Mf',    # Мафія (Mafia)
    'D': 'D'       # Дон (Don)
}


class SupabaseAPI:
    """Simple Supabase REST API client."""
    
    def __init__(self, url: str, key: str):
        self.url = url.rstrip('/')
        self.headers = {
            'apikey': key,
            'Authorization': f'Bearer {key}',
            'Content-Type': 'application/json',
            'Prefer': 'return=representation'
        }
    
    def get(self, table: str, **params):
        """GET request to Supabase table."""
        url = f'{self.url}/rest/v1/{table}'
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()
    
    def post(self, table: str, data):
        """POST request to Supabase table."""
        url = f'{self.url}/rest/v1/{table}'
        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()
    
    def delete(self, table: str, **params):
        """DELETE request to Supabase table."""
        url = f'{self.url}/rest/v1/{table}'
        response = requests.delete(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response


def parse_csv(text: str) -> List[List[str]]:
    """Parse CSV text into a 2D list."""
    rows = []
    current_row = []
    current_field = ''
    in_quotes = False
    
    for i, char in enumerate(text):
        next_char = text[i + 1] if i + 1 < len(text) else None
        
        if char == '"':
            if in_quotes and next_char == '"':
                current_field += '"'
            else:
                in_quotes = not in_quotes
        elif char == ',' and not in_quotes:
            current_row.append(current_field)
            current_field = ''
        elif (char == '\n' or char == '\r') and not in_quotes:
            if char == '\r' and next_char == '\n':
                continue
            current_row.append(current_field)
            if current_row and (len(current_row) > 1 or current_row[0]):
                rows.append(current_row)
            current_row = []
            current_field = ''
        else:
            current_field += char
    
    if current_field or current_row:
        current_row.append(current_field)
        if current_row and (len(current_row) > 1 or current_row[0]):
            rows.append(current_row)
    
    return rows


def fetch_spreadsheet_data() -> List[List[str]]:
    """Fetch CSV data from Google Sheets."""
    csv_url = f'https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={SHEET_GID}'
    
    response = requests.get(csv_url, timeout=30)
    
    if not response.ok:
        raise Exception(f"Failed to fetch spreadsheet: HTTP {response.status_code}")
    
    response.encoding = 'utf-8'
    csv_text = response.text
    
    if csv_text.strip().startswith('<'):
        raise Exception("Received HTML instead of CSV. Check if spreadsheet is publicly accessible.")
    
    return parse_csv(csv_text)


def is_stats_column(header: str) -> bool:
    """Check if this column is a stats column (starts with M+, M-, etc) and not game data."""
    if not header:
        return False
    return header.strip() in ['M+', 'M-', 'Ш+', 'Ш-', 'Мф+', 'Мф-', 'Д+', 'Д-', 'Sh+', 'Sh-', 'Mf+', 'Mf-', 'D+', 'D-']


def parse_game_header(header: str) -> Tuple[Optional[int], Optional[str]]:
    """
    Parse game number and date from header cell.
    Expected formats: 
    - "#34" (old format - returns game_number only, date=None)
    - "#34 15.01.2025" (new format - returns both game_number and date)
    Returns: (game_number, date_string) tuple or (None, None) if not found
    Date string is in ISO format (YYYY-MM-DD) for database storage
    """
    if not header:
        return (None, None)
    
    header = header.strip()
    
    # Look for format like "#34" or "#34 15.01.2025"
    if header.startswith('#'):
        try:
            parts = header[1:].split()  # Split after removing #
            
            # Parse game number (first part)
            game_number = int(parts[0])
            
            # Parse date if present (second part)
            game_date = None
            if len(parts) >= 2:
                date_str = parts[1]
                # Parse dd.MM.yyyy format
                date_parts = date_str.split('.')
                if len(date_parts) == 3:
                    day, month, year = date_parts
                    # Convert to ISO format (YYYY-MM-DD)
                    game_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            
            return (game_number, game_date)
        except (ValueError, IndexError):
            return (None, None)
    
    return (None, None)


def parse_role_outcome(cell: str) -> Optional[Tuple[str, bool]]:
    """
    Parse cell value to extract role code and outcome.
    Returns: (role_code, won) or None if invalid
    """
    if not cell or len(cell) < 2:
        return None
    
    outcome = cell[-1]
    if outcome not in ['+', '-']:
        return None
    
    role_part = cell[:-1]
    
    if role_part not in ROLE_CODES:
        return None
    
    won = (outcome == '+')
    return (ROLE_CODES[role_part], won)


def determine_mafia_won(players_data: List[Tuple[str, str, bool]]) -> bool:
    """Determine if mafia won the game based on player outcomes."""
    for _, role_code, won in players_data:
        if won:
            if role_code in ['M', 'Sh']:
                return False
            elif role_code in ['Mf', 'D']:
                return True
    return False


def get_or_create_player(api: SupabaseAPI, name: str, player_cache: Dict[str, int]) -> int:
    """Get existing player ID or create new player."""
    name = name.strip()
    
    if name in player_cache:
        return player_cache[name]
    
    existing = api.get('player', name=f'eq.{name}')
    if existing:
        player_id = existing[0]['id']
        player_cache[name] = player_id
        return player_id
    
    result = api.post('player', {'name': name})
    player_id = result[0]['id']
    player_cache[name] = player_id
    return player_id


def get_role_id(api: SupabaseAPI, role_code: str, role_cache: Dict[str, int]) -> int:
    """Get role ID by code."""
    if role_code in role_cache:
        return role_cache[role_code]
    
    result = api.get('role', code=f'eq.{role_code}')
    if not result:
        raise Exception(f"Role code '{role_code}' not found in database")
    
    role_id = result[0]['id']
    role_cache[role_code] = role_id
    return role_id


def get_db_stats(api: SupabaseAPI) -> Dict[str, int]:
    """Get statistics about current database state."""
    games = api.get('game', select='id')
    players = api.get('player', select='id')
    
    return {
        'games_in_db': len(games),
        'players_in_db': len(players)
    }


def get_spreadsheet_stats(rows: List[List[str]]) -> Dict[str, int]:
    """Parse spreadsheet and return statistics about available games."""
    if len(rows) < 2:
        return {
            'games_in_sheet': 0,
            'valid_games': 0,
            'invalid_games': 0
        }
    
    header_row = rows[0]
    player_rows = rows[1:]
    
    # Find the first stats column
    last_game_col = len(header_row)
    for col_idx in range(1, len(header_row)):
        if is_stats_column(header_row[col_idx]):
            last_game_col = col_idx
            break
    
    valid_games = 0
    invalid_games = 0
    
    for col_idx in range(1, last_game_col):
        players_data = []
        for row in player_rows:
            if col_idx >= len(row):
                continue
            
            player_name = row[0].strip()
            cell_value = row[col_idx].strip()
            
            if not player_name or not cell_value:
                continue
            
            role_outcome = parse_role_outcome(cell_value)
            if role_outcome:
                role_code, won = role_outcome
                players_data.append((player_name, role_code, won))
        
        if not players_data:
            continue
        
        if len(players_data) == 10:
            valid_games += 1
        else:
            invalid_games += 1
    
    return {
        'games_in_sheet': valid_games + invalid_games,
        'valid_games': valid_games,
        'invalid_games': invalid_games
    }


def clear_all_data(api: SupabaseAPI):
    """Clear all game data from database."""
    try:
        api.delete('game_player', id=f'gte.0')
    except Exception:
        pass
    
    try:
        api.delete('game', id=f'gte.0')
    except Exception:
        pass
    
    try:
        api.delete('player', id=f'gte.0')
    except Exception:
        pass


def sync_games(mode: str = 'sync') -> Dict[str, any]:
    """
    Main sync function that imports games from spreadsheet to database.
    
    Args:
        mode: 'sync' for incremental updates, 'overwrite' to clear and reimport all
    
    Returns:
        Dictionary with statistics:
        {
            'success': bool,
            'mode': str,
            'games_in_db_before': int,
            'games_in_db_after': int,
            'games_in_sheet': int,
            'valid_games': int,
            'invalid_games': int,
            'games_synced': int,
            'games_skipped': int,
            'players_created': int,
            'error': str (if success=False)
        }
    """
    
    if not SUPABASE_KEY:
        return {
            'success': False,
            'error': 'SUPABASE_KEY not set in environment variables'
        }
    
    try:
        # Initialize API client
        api = SupabaseAPI(SUPABASE_URL, SUPABASE_KEY)
        
        # Get initial DB stats
        db_stats_before = get_db_stats(api)
        
        # Fetch spreadsheet data
        rows = fetch_spreadsheet_data()
        
        if len(rows) < 2:
            return {
                'success': False,
                'error': 'Spreadsheet has insufficient data'
            }
        
        header_row = rows[0]
        player_rows = rows[1:]
        
        # Get spreadsheet stats
        sheet_stats = get_spreadsheet_stats(rows)
        
        # Clear data if in overwrite mode
        if mode == 'overwrite':
            clear_all_data(api)
        
        # Cache for players and roles
        player_cache = {}
        role_cache = {}
        
        # Track initial player count
        players_before = len(api.get('player', select='id'))
        
        # Find the first stats column
        last_game_col = len(header_row)
        for col_idx in range(1, len(header_row)):
            if is_stats_column(header_row[col_idx]):
                last_game_col = col_idx
                break
        
        # Process each game column
        games_synced = 0
        games_skipped = 0
        
        for col_idx in range(1, last_game_col):
            # Parse game number and date from header
            game_number = None
            game_date = None
            if col_idx < len(header_row):
                game_number, game_date = parse_game_header(header_row[col_idx])
            
            # Collect all players for this game
            players_data = []
            for row in player_rows:
                if col_idx >= len(row):
                    continue
                
                player_name = row[0].strip()
                cell_value = row[col_idx].strip()
                
                if not player_name or not cell_value:
                    continue
                
                role_outcome = parse_role_outcome(cell_value)
                if not role_outcome:
                    continue
                
                role_code, won = role_outcome
                players_data.append((player_name, role_code, won))
            
            # Skip empty columns or invalid games
            if not players_data:
                continue
            
            if len(players_data) != 10:
                games_skipped += 1
                continue
            
            # Check if game already exists (skip in sync mode)
            if mode == 'sync':
                existing = api.get('game', spreadsheet_column=f'eq.{col_idx}')
                if existing:
                    games_skipped += 1
                    continue
            
            # Import the game
            try:
                mafia_won = determine_mafia_won(players_data)
                game_data = {
                    'mafia_won': mafia_won,
                    'game_date': game_date,  # Use parsed date or None
                    'spreadsheet_column': col_idx
                }
                
                # Add game_number if parsed
                if game_number is not None:
                    game_data['game_number'] = game_number
                
                game_result = api.post('game', game_data)
                game_id = game_result[0]['id']
                
                # Create game_player records
                game_player_records = []
                for player_name, role_code, won in players_data:
                    player_id = get_or_create_player(api, player_name, player_cache)
                    role_id = get_role_id(api, role_code, role_cache)
                    game_player_records.append({
                        'game_id': game_id,
                        'player_id': player_id,
                        'role_id': role_id
                    })
                
                if game_player_records:
                    api.post('game_player', game_player_records)
                
                games_synced += 1
            except Exception as e:
                # Continue on error for individual games
                continue
        
        # Get final stats
        db_stats_after = get_db_stats(api)
        players_after = len(api.get('player', select='id'))
        
        return {
            'success': True,
            'mode': mode,
            'games_in_db_before': db_stats_before['games_in_db'],
            'games_in_db_after': db_stats_after['games_in_db'],
            'games_in_sheet': sheet_stats['games_in_sheet'],
            'valid_games': sheet_stats['valid_games'],
            'invalid_games': sheet_stats['invalid_games'],
            'games_synced': games_synced,
            'games_skipped': games_skipped,
            'players_created': players_after - players_before,
            'players_total': players_after
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

