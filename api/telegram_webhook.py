"""
Vercel serverless function for handling Telegram bot webhooks.
Receives commands from authorized users and triggers GitHub workflows.
"""

import os
import json
import requests
import math
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass

# Configuration from environment variables
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
GITHUB_REPO = os.environ.get('GITHUB_REPO', '')  # Format: "username/repo"
ALLOWED_USER_IDS = os.environ.get('ALLOWED_USER_IDS', '5980607330,184403698')
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://mpasyybxqvzbnxciejqo.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')

# Parse allowed user IDs
ALLOWED_USERS = set(int(uid.strip()) for uid in ALLOWED_USER_IDS.split(',') if uid.strip())


# ============================================================================
# SUPABASE API CLIENT
# ============================================================================

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
        # Base headers for GET requests (Range will be added per request)
        self.get_headers = {
            'apikey': key,
            'Authorization': f'Bearer {key}',
            'Content-Type': 'application/json'
        }
    
    def get(self, table: str, **params):
        """GET request to Supabase table with automatic pagination."""
        url = f'{self.url}/rest/v1/{table}'
        
        all_results = []
        offset = 0
        page_size = 1000
        
        while True:
            # Fetch one page
            headers = {**self.get_headers, 'Range': f'{offset}-{offset + page_size - 1}'}
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            page_data = response.json()
            if not page_data:
                break
                
            all_results.extend(page_data)
            
            # Check if we got a full page (meaning there might be more)
            if len(page_data) < page_size:
                break
                
            offset += page_size
        
        return all_results
    
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


# ============================================================================
# GLICKO-2 RATING ENGINE
# ============================================================================

# Glicko-2 Constants
INITIAL_RATING = 1500.0
INITIAL_RD = 225.0  # Updated from 350.0
INITIAL_SIGMA = 0.06
TAU = 1.25  # Updated from 0.5 (higher volatility)
WEIGHT_MULTIPLIER = 1.75  # Multiplier for micromatch weights
EPSILON = 0.000001  # Convergence tolerance


@dataclass
class PlayerRating:
    """Represents a player's Glicko-2 rating."""
    player_id: int
    rating: float = INITIAL_RATING
    rd: float = INITIAL_RD
    sigma: float = INITIAL_SIGMA
    
    def to_glicko2_scale(self) -> Tuple[float, float]:
        """Convert from Glicko scale to Glicko-2 scale."""
        mu = (self.rating - 1500) / 173.7178
        phi = self.rd / 173.7178
        return mu, phi
    
    @staticmethod
    def from_glicko2_scale(mu: float, phi: float, sigma: float) -> Tuple[float, float, float]:
        """Convert from Glicko-2 scale back to Glicko scale."""
        rating = mu * 173.7178 + 1500
        rd = phi * 173.7178
        return rating, rd, sigma


def g_function(phi: float) -> float:
    """Glicko-2 g function."""
    return 1.0 / math.sqrt(1.0 + 3.0 * phi * phi / (math.pi * math.pi))


def e_function(mu: float, mu_j: float, phi_j: float) -> float:
    """Glicko-2 E function."""
    return 1.0 / (1.0 + math.exp(-g_function(phi_j) * (mu - mu_j)))


def compute_variance(mu: float, opponents: List[Tuple[float, float]], weights: List[float]) -> float:
    """Compute the estimated variance of the player's rating with weights."""
    v_inv = 0.0
    for (mu_j, phi_j), weight in zip(opponents, weights):
        g = g_function(phi_j)
        e = e_function(mu, mu_j, phi_j)
        v_inv += weight * g * g * e * (1.0 - e)
    
    if v_inv < EPSILON:
        return 1e6
    
    return 1.0 / v_inv


def compute_delta(mu: float, v: float, opponents: List[Tuple[float, float]], 
                  results: List[float], weights: List[float]) -> float:
    """Compute the improvement in rating based on game outcomes with weights."""
    delta_sum = 0.0
    for (mu_j, phi_j), s, weight in zip(opponents, results, weights):
        g = g_function(phi_j)
        e = e_function(mu, mu_j, phi_j)
        delta_sum += weight * g * (s - e)
    
    return v * delta_sum


def compute_new_sigma(phi: float, sigma: float, v: float, delta: float) -> float:
    """Compute new volatility using Illinois algorithm."""
    a = math.log(sigma * sigma)
    
    def f(x):
        ex = math.exp(x)
        phi2 = phi * phi
        v_inv = 1.0 / v
        d2 = delta * delta
        
        term1 = ex * (d2 - phi2 - v - ex)
        term2 = 2.0 * (phi2 + v + ex) * (phi2 + v + ex)
        term3 = (x - a) / (TAU * TAU)
        
        return term1 / term2 - term3
    
    A = a
    if delta * delta > phi * phi + v:
        B = math.log(delta * delta - phi * phi - v)
    else:
        k = 1
        while f(a - k * TAU) < 0:
            k += 1
        B = a - k * TAU
    
    fA = f(A)
    fB = f(B)
    
    while abs(B - A) > EPSILON:
        C = A + (A - B) * fA / (fB - fA)
        fC = f(C)
        
        if fC * fB < 0:
            A = B
            fA = fB
        else:
            fA = fA / 2.0
        
        B = C
        fB = fC
    
    return math.exp(A / 2.0)


def update_rating(player: PlayerRating, opponents: List[PlayerRating], 
                  results: List[float], weights: List[float]) -> PlayerRating:
    """Update a player's rating based on game results using Glicko-2 with weights."""
    if not opponents or not results:
        mu, phi = player.to_glicko2_scale()
        phi_star = math.sqrt(phi * phi + player.sigma * player.sigma)
        rating, rd, sigma = PlayerRating.from_glicko2_scale(mu, phi_star, player.sigma)
        return PlayerRating(player.player_id, rating, rd, sigma)
    
    mu, phi = player.to_glicko2_scale()
    opponent_ratings = [opp.to_glicko2_scale() for opp in opponents]
    
    v = compute_variance(mu, opponent_ratings, weights)
    delta = compute_delta(mu, v, opponent_ratings, results, weights)
    new_sigma = compute_new_sigma(phi, player.sigma, v, delta)
    phi_star = math.sqrt(phi * phi + new_sigma * new_sigma)
    phi_new = 1.0 / math.sqrt(1.0 / (phi_star * phi_star) + 1.0 / v)
    
    # Compute weighted sum for mu update
    weighted_sum = 0.0
    for (mu_j, phi_j), s, weight in zip(opponent_ratings, results, weights):
        g = g_function(phi_j)
        e = e_function(mu, mu_j, phi_j)
        weighted_sum += weight * g * (s - e)
    
    mu_new = mu + phi_new * phi_new * weighted_sum
    
    rating, rd, sigma = PlayerRating.from_glicko2_scale(mu_new, phi_new, new_sigma)
    return PlayerRating(player.player_id, rating, rd, sigma)


def process_game(game_id: int, players_data: List[Tuple[int, bool]], 
                 current_ratings: Dict[int, PlayerRating]) -> Dict[int, Tuple[PlayerRating, PlayerRating]]:
    """
    Process a single game and compute rating changes for all players.
    
    Uses WEIGHTED micromatch approach with NORMALIZATION:
    - Red team (7 players): each plays 3 matches with weight = WEIGHT_MULTIPLIER / 3
    - Black team (3 players): each plays 7 matches with weight = WEIGHT_MULTIPLIER / 7
    - NO matches between teammates
    - Normalization forces total rating change = 0 (zero-sum)
    """
    if len(players_data) != 10:
        raise ValueError(f"Game {game_id} must have exactly 10 players, got {len(players_data)}")
    
    # Count team sizes for weight calculation
    winners = [pid for pid, won in players_data if won]
    losers = [pid for pid, won in players_data if not won]
    winner_count = len(winners)
    loser_count = len(losers)
    
    # Step 1: Calculate tentative rating changes with weights
    tentative_results = {}
    
    for player_id, player_won in players_data:
        if player_id not in current_ratings:
            current_ratings[player_id] = PlayerRating(player_id)
        
        rating_before = current_ratings[player_id]
        opponents = []
        game_results = []
        weights = []
        
        # Calculate weight per micromatch
        # Winner faces loser_count opponents, loser faces winner_count opponents
        opponent_count = loser_count if player_won else winner_count
        weight_per_match = WEIGHT_MULTIPLIER / opponent_count
        
        for other_id, other_won in players_data:
            if other_id == player_id:
                continue
            
            # ONLY match against opposing team
            if player_won == other_won:
                continue  # Skip teammates
            
            if other_id not in current_ratings:
                current_ratings[other_id] = PlayerRating(other_id)
            
            opponents.append(current_ratings[other_id])
            game_results.append(1.0 if player_won else 0.0)
            weights.append(weight_per_match)
        
        rating_after = update_rating(rating_before, opponents, game_results, weights)
        tentative_results[player_id] = (rating_before, rating_after)
    
    # Step 2: Normalize to force zero-sum
    total_change = sum(
        tentative_results[pid][1].rating - tentative_results[pid][0].rating
        for pid, _ in players_data
    )
    correction = total_change / 10.0
    
    # Step 3: Apply normalization and update current_ratings
    results = {}
    for player_id, _ in players_data:
        rating_before, rating_after_tentative = tentative_results[player_id]
        
        # Apply correction
        normalized_rating = rating_after_tentative.rating - correction
        rating_after_final = PlayerRating(
            player_id,
            normalized_rating,
            rating_after_tentative.rd,
            rating_after_tentative.sigma
        )
        
        results[player_id] = (rating_before, rating_after_final)
        current_ratings[player_id] = rating_after_final
    
    return results


def full_recompute(api) -> bool:
    """Perform full rating recomputation from scratch."""
    try:
        print("Starting full rating recomputation...")
        
        print("Deleting existing rating history...")
        try:
            api.delete('player_rating_history', id='gte.0')
        except Exception:
            pass
        
        print("Fetching all games...")
        games = api.get('game', select='id,mafia_won', order='id.asc')
        
        if not games:
            print("No games found.")
            return True
        
        print(f"Found {len(games)} games to process.")
        
        print("Fetching game player data...")
        game_players = api.get('game_player', select='game_id,player_id,role_id')
        
        roles = api.get('role', select='id,code')
        role_map = {r['id']: r['code'] for r in roles}
        
        games_data = {}
        for gp in game_players:
            game_id = gp['game_id']
            if game_id not in games_data:
                games_data[game_id] = []
            games_data[game_id].append(gp)
        
        current_ratings: Dict[int, PlayerRating] = {}
        rating_history_records = []
        
        for idx, game in enumerate(games, 1):
            game_id = game['id']
            mafia_won = game['mafia_won']
            
            if game_id not in games_data:
                continue
            
            players_in_game = games_data[game_id]
            
            if len(players_in_game) != 10:
                print(f"Warning: Game {game_id} has {len(players_in_game)} players, skipping.")
                continue
            
            players_data = []
            for gp in players_in_game:
                player_id = gp['player_id']
                role_code = role_map[gp['role_id']]
                
                if role_code in ['M', 'Sh']:
                    won = not mafia_won
                else:
                    won = mafia_won
                
                players_data.append((player_id, won))
            
            try:
                results = process_game(game_id, players_data, current_ratings)
                
                for player_id, (before, after) in results.items():
                    rating_history_records.append({
                        'game_id': game_id,
                        'player_id': player_id,
                        'rating_before': round(before.rating, 2),
                        'rd_before': round(before.rd, 2),
                        'sigma_before': round(before.sigma, 6),
                        'rating_after': round(after.rating, 2),
                        'rd_after': round(after.rd, 2),
                        'sigma_after': round(after.sigma, 6)
                    })
            
            except Exception as e:
                print(f"Error processing game {game_id}: {e}")
                continue
            
            if idx % 10 == 0:
                print(f"Processed {idx}/{len(games)} games...")
        
        if rating_history_records:
            print(f"Inserting {len(rating_history_records)} rating history records...")
            batch_size = 100
            for i in range(0, len(rating_history_records), batch_size):
                batch = rating_history_records[i:i+batch_size]
                api.post('player_rating_history', batch)
            
            print("Rating history inserted successfully.")
        
        print(f"Full recomputation complete! Processed {len(games)} games, {len(current_ratings)} players.")
        return True
        
    except Exception as e:
        print(f"Error during full recomputation: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# SYNC ENGINE
# ============================================================================

SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID', '1FJ9T5Zgh5_yS_G-Dx_FAP12RRXsH3IG45WCoZUcaHgA')
SHEET_GID = os.environ.get('SHEET_GID', '216801262')

# Role code mapping
ROLE_CODES = {
    'M': 'M',      # Мірны жыхар (Citizen)
    'Sh': 'Sh',    # Шэрыф (Sheriff)
    'Mf': 'Mf',    # Мафія (Mafia)
    'D': 'D'       # Дон (Don)
}


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


def sync_games(mode: str = 'sync') -> Dict[str, Any]:
    """
    Main sync function that imports games from spreadsheet to database.
    
    Args:
        mode: 'sync' for incremental updates, 'overwrite' to clear and reimport all
    
    Returns:
        Dictionary with statistics
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
                    'game_date': game_date,
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
                print(f"Error syncing game at column {col_idx}: {e}")
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
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': str(e)
        }


# ============================================================================
# TELEGRAM BOT FUNCTIONS
# ============================================================================

def send_telegram_message(chat_id: int, text: str, reply_markup: Dict = None) -> bool:
    """Send a message to Telegram chat."""
    if not TELEGRAM_BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN is not set!")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    
    print(f"Sending message to chat_id={chat_id}, has_keyboard={reply_markup is not None}")
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        print(f"Telegram API response: status={response.status_code}")
        if not response.ok:
            print(f"Telegram API error: {response.text}")
        return response.ok
    except Exception as e:
        print(f"Error sending message: {e}")
        import traceback
        traceback.print_exc()
        return False


def edit_telegram_message(chat_id: int, message_id: int, text: str, reply_markup: Dict = None) -> bool:
    """Edit an existing Telegram message."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.ok
    except Exception as e:
        print(f"Error editing message: {e}")
        return False


def answer_callback_query(callback_query_id: str, text: str = "") -> bool:
    """Answer a callback query to remove the loading state."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery"
    payload = {
        "callback_query_id": callback_query_id,
        "text": text
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.ok
    except Exception as e:
        print(f"Error answering callback: {e}")
        return False


def trigger_github_workflow(mode: str, chat_id: int) -> bool:
    """Trigger GitHub workflow via repository_dispatch."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/dispatches"
    
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {GITHUB_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "event_type": mode,  # "sync" or "overwrite"
        "client_payload": {
            "chat_id": str(chat_id),
            "mode": mode
        }
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        return response.status_code in [200, 204]
    except Exception as e:
        print(f"Error triggering workflow: {e}")
        return False


def get_supabase_setting(key: str, default: str = None) -> str:
    """Get a setting from Supabase app_settings table."""
    try:
        url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/app_settings"
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
        }
        params = {'key': f'eq.{key}'}
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.ok:
            data = response.json()
            if data and len(data) > 0:
                return data[0].get('value', default)
        return default
    except Exception as e:
        print(f"Error getting setting: {e}")
        return default


def update_supabase_setting(key: str, value: str) -> bool:
    """Update a setting in Supabase app_settings table."""
    try:
        url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/rpc/update_setting"
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'application/json'
        }
        payload = {
            'setting_key': key,
            'setting_value': value
        }
        
        print(f"Updating setting: {key} = {value}")
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        print(f"Update response: status={response.status_code}, ok={response.ok}")
        if not response.ok:
            print(f"Update error response: {response.text}")
        return response.ok
    except Exception as e:
        print(f"Error updating setting: {e}")
        import traceback
        traceback.print_exc()
        return False


def get_all_players() -> list:
    """Get all players from Supabase."""
    try:
        url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/player"
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
        }
        params = {'select': 'id,name,is_hidden', 'order': 'name.asc'}
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.ok:
            return response.json()
        return []
    except Exception as e:
        print(f"Error getting players: {e}")
        return []


def get_hidden_players() -> list:
    """Get all hidden players from Supabase."""
    try:
        url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/player"
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
        }
        params = {'select': 'id,name', 'is_hidden': 'eq.true', 'order': 'name.asc'}
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.ok:
            return response.json()
        return []
    except Exception as e:
        print(f"Error getting hidden players: {e}")
        return []


def update_player_hidden_status(player_name: str, is_hidden: bool) -> bool:
    """Update a player's hidden status in Supabase."""
    try:
        url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/player"
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'application/json',
            'Prefer': 'return=representation'
        }
        params = {'name': f'eq.{player_name}'}
        payload = {'is_hidden': is_hidden}
        
        response = requests.patch(url, headers=headers, params=params, json=payload, timeout=10)
        return response.ok
    except Exception as e:
        print(f"Error updating player hidden status: {e}")
        return False


def clear_all_hidden_players() -> int:
    """Unhide all hidden players. Returns count of players unhidden."""
    try:
        # First, get count of hidden players
        hidden_players = get_hidden_players()
        count = len(hidden_players)
        
        if count == 0:
            return 0
        
        # Update all hidden players to not hidden
        url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/player"
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'application/json'
        }
        params = {'is_hidden': 'eq.true'}
        payload = {'is_hidden': False}
        
        response = requests.patch(url, headers=headers, params=params, json=payload, timeout=10)
        if response.ok:
            return count
        return 0
    except Exception as e:
        print(f"Error clearing hidden players: {e}")
        return 0


def handle_start_command(chat_id: int, user_id: int) -> Dict[str, Any]:
    """Handle /start command - show menu with buttons."""
    print(f"handle_start_command: user_id={user_id}, allowed_users={ALLOWED_USERS}")
    
    if user_id not in ALLOWED_USERS:
        print(f"User {user_id} is not authorized")
        send_telegram_message(
            chat_id,
            "❌ Вы не маеце доступу да гэтага бота."
        )
        return {"statusCode": 200}
    
    print(f"User {user_id} is authorized, sending menu")
    
    # Get current threshold value
    current_threshold = get_supabase_setting('min_games_threshold', '25')
    
    # Get current activity period value
    current_activity_period = get_supabase_setting('activity_period_days', '30')
    
    # Create inline keyboard with six buttons
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🔄 Сінхранізаваць", "callback_data": "sync"}
            ],
            [
                {"text": "⚠️ Перазапісаць", "callback_data": "overwrite"}
            ],
            [
                {"text": "🏆 Пералічыць рэйтынг", "callback_data": "recompute_rating"}
            ],
            [
                {"text": f"⚙️ Змяніць заліковы мінімум ({current_threshold})", "callback_data": "change_threshold"}
            ],
            [
                {"text": f"⏰ Змяніць перыяд актыўнасці ({current_activity_period})", "callback_data": "change_activity_period"}
            ],
            [
                {"text": "👁️ Схаваныя гульцы", "callback_data": "hidden_players_menu"}
            ]
        ]
    }
    
    message = (
        "🎭 <b>Mafia Stats Bot</b>\n\n"
        "Выберыце дзеянне:\n\n"
        "<b>Сінхранізаваць</b> - дадаць новыя гульні з табліцы\n"
        "<b>Перазапісаць</b> - выдаліць усё і загрузіць зноў\n"
        "<b>Пералічыць рэйтынг</b> - пералічыць Glicko-2 рэйтынгі\n"
        f"<b>Заліковы мінімум</b> - зараз: {current_threshold} гульняў\n"
        f"<b>Перыяд актыўнасці</b> - зараз: {current_activity_period} дзён\n"
        "<b>Схаваныя гульцы</b> - кіраванне схаванымі гульцамі"
    )
    
    success = send_telegram_message(chat_id, message, keyboard)
    print(f"send_telegram_message returned: {success}")
    return {"statusCode": 200}


# Store user states for threshold input and hidden players management
user_states = {}


def show_hidden_players_menu(chat_id: int, message_id: int = None) -> bool:
    """Show the hidden players submenu."""
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🚫 Схаваць гульца", "callback_data": "hide_player"}
            ],
            [
                {"text": "✅ Адкрыць гульца", "callback_data": "unhide_player"}
            ],
            [
                {"text": "📋 Паказаць спіс схаваных", "callback_data": "view_hidden"}
            ],
            [
                {"text": "👥 Паказаць усіх гульцоў", "callback_data": "view_all_players"}
            ],
            [
                {"text": "🗑️ Ачысціць усё", "callback_data": "clear_hidden"}
            ],
            [
                {"text": "⬅️ Назад", "callback_data": "back_to_main"}
            ]
        ]
    }
    
    message = (
        "👁️ <b>Схаваныя гульцы</b>\n\n"
        "Выберыце дзеянне:\n\n"
        "<b>Схаваць гульца</b> - схаваць гульца з галоўнай табліцы\n"
        "<b>Адкрыць гульца</b> - вярнуць гульца ў табліцу\n"
        "<b>Паказаць спіс схаваных</b> - паглядзець усіх схаваных гульцоў\n"
        "<b>Паказаць усіх гульцоў</b> - паглядзець усіх гульцоў (🥷 = схаваны)\n"
        "<b>Ачысціць усё</b> - адкрыць усіх схаваных гульцоў"
    )
    
    if message_id:
        return edit_telegram_message(chat_id, message_id, message, keyboard)
    else:
        return send_telegram_message(chat_id, message, keyboard)


def handle_callback_query(callback_query: Dict) -> Dict[str, Any]:
    """Handle button callback."""
    query_id = callback_query.get("id")
    data = callback_query.get("data")
    message = callback_query.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    message_id = message.get("message_id")
    user_id = callback_query.get("from", {}).get("id")
    
    # Validate user
    if user_id not in ALLOWED_USERS:
        answer_callback_query(query_id, "Доступ забаронены")
        return {"statusCode": 200}
    
    # Answer the callback query
    answer_callback_query(query_id)
    
    # Handle different callback types
    if data == "change_threshold":
        # Ask user to input new threshold
        user_states[user_id] = {"waiting_for": "threshold", "message_id": message_id}
        
        current_threshold = get_supabase_setting('min_games_threshold', '25')
        prompt_text = (
            "⚙️ <b>Змена заліковага мінімуму</b>\n\n"
            f"Цяперашняе значэнне: <b>{current_threshold}</b> гульняў\n\n"
            "Увядзіце новае значэнне (лік ад 0 да 100):"
        )
        
        edit_telegram_message(chat_id, message_id, prompt_text)
        return {"statusCode": 200}
    
    elif data == "change_activity_period":
        # Ask user to input new activity period
        user_states[user_id] = {"waiting_for": "activity_period", "message_id": message_id}
        
        current_activity_period = get_supabase_setting('activity_period_days', '30')
        prompt_text = (
            "⏰ <b>Змена перыяду актыўнасці</b>\n\n"
            f"Цяперашняе значэнне: <b>{current_activity_period}</b> дзён\n\n"
            "Увядзіце новае значэнне (лік ад 1 да 365):"
        )
        
        edit_telegram_message(chat_id, message_id, prompt_text)
        return {"statusCode": 200}
    
    elif data == "hidden_players_menu":
        # Show hidden players menu
        show_hidden_players_menu(chat_id, message_id)
        return {"statusCode": 200}
    
    elif data == "hide_player":
        # Ask user to input player name to hide
        user_states[user_id] = {"waiting_for": "hide_player"}
        prompt_text = (
            "🚫 <b>Схаваць гульца</b>\n\n"
            "Увядзіце імя гульца, якога трэба схаваць з галоўнай табліцы:"
        )
        edit_telegram_message(chat_id, message_id, prompt_text)
        return {"statusCode": 200}
    
    elif data == "unhide_player":
        # Ask user to input player name to unhide
        user_states[user_id] = {"waiting_for": "unhide_player"}
        prompt_text = (
            "✅ <b>Адкрыць гульца</b>\n\n"
            "Увядзіце імя гульца, якога трэба вярнуць у галоўную табліцу:"
        )
        edit_telegram_message(chat_id, message_id, prompt_text)
        return {"statusCode": 200}
    
    elif data == "view_hidden":
        # Show list of hidden players
        hidden_players = get_hidden_players()
        
        if not hidden_players:
            message_text = (
                "📋 <b>Спіс схаваных гульцоў</b>\n\n"
                "Няма схаваных гульцоў.\n\n"
                "Выкарыстайце /start для вяртання ў меню."
            )
        else:
            player_list = "\n".join([f"• {p['name']}" for p in hidden_players])
            message_text = (
                "📋 <b>Спіс схаваных гульцоў</b>\n\n"
                f"Усяго схавана: <b>{len(hidden_players)}</b>\n\n"
                f"{player_list}\n\n"
                "Выкарыстайце /start для вяртання ў меню."
            )
        
        edit_telegram_message(chat_id, message_id, message_text)
        return {"statusCode": 200}
    
    elif data == "view_all_players":
        # Show list of all players with ninja icon for hidden ones
        all_players = get_all_players()
        
        if not all_players:
            message_text = (
                "👥 <b>Усе гульцы</b>\n\n"
                "Няма гульцоў у базе дадзеных.\n\n"
                "Выкарыстайце /start для вяртання ў меню."
            )
        else:
            # Sort players by name
            all_players.sort(key=lambda p: p['name'])
            
            # Format player list with ninja icon for hidden players
            player_list = "\n".join([
                f"🥷 {p['name']}" if p.get('is_hidden', False) else f"• {p['name']}"
                for p in all_players
            ])
            
            hidden_count = sum(1 for p in all_players if p.get('is_hidden', False))
            visible_count = len(all_players) - hidden_count
            
            message_text = (
                "👥 <b>Усе гульцы</b>\n\n"
                f"Усяго гульцоў: <b>{len(all_players)}</b>\n"
                f"Адкрытых: <b>{visible_count}</b> | Схаваных: <b>{hidden_count}</b>\n\n"
                f"{player_list}\n\n"
                "🥷 - схаваны гулец\n\n"
                "Выкарыстайце /start для вяртання ў меню."
            )
        
        edit_telegram_message(chat_id, message_id, message_text)
        return {"statusCode": 200}
    
    elif data == "clear_hidden":
        # Clear all hidden players
        count = clear_all_hidden_players()
        
        if count == 0:
            message_text = (
                "ℹ️ <b>Няма схаваных гульцоў</b>\n\n"
                "Усе гульцы ужо адлюстроўваюцца ў табліцы.\n\n"
                "Выкарыстайце /start для вяртання ў меню."
            )
        else:
            message_text = (
                "✅ <b>Усе гульцы адкрытыя!</b>\n\n"
                f"Адкрыта гульцоў: <b>{count}</b>\n\n"
                "Усе гульцы цяпер будуць адлюстроўвацца ў галоўнай табліцы.\n\n"
                "Выкарыстайце /start для вяртання ў меню."
            )
        
        edit_telegram_message(chat_id, message_id, message_text)
        return {"statusCode": 200}
    
    elif data == "back_to_main":
        # Go back to main menu
        handle_start_command(chat_id, user_id)
        return {"statusCode": 200}
    
    elif data == "recompute_rating":
        # Recompute all ratings from scratch
        edit_telegram_message(chat_id, message_id, "⏳ <b>Пералік рэйтынгу...</b>\n\nКалі ласка, пачакайце.")
        
        try:
            # Create API instance
            api = SupabaseAPI(SUPABASE_URL, SUPABASE_KEY)
            
            # Run full recomputation
            success = full_recompute(api)
            
            if success:
                edit_telegram_message(
                    chat_id, 
                    message_id,
                    "✅ <b>Рэйтынг пералічаны!</b>\n\n"
                    "Усе рэйтынгі Glicko-2 адноўленыя.\n\n"
                    "Выкарыстайце /start для вяртання ў меню."
                )
            else:
                edit_telegram_message(
                    chat_id, 
                    message_id,
                    "❌ <b>Памылка пры пераліку рэйтынгу</b>\n\n"
                    "Не атрымалася пералічыць рэйтынгі.\n\n"
                    "Выкарыстайце /start для вяртання ў меню."
                )
        except Exception as e:
            print(f"Error in rating recomputation: {e}")
            import traceback
            traceback.print_exc()
            edit_telegram_message(
                chat_id, 
                message_id,
                f"❌ <b>Памылка</b>\n\n{str(e)}\n\nВыкарыстайце /start для вяртання ў меню."
            )
        
        return {"statusCode": 200}
    
    # Determine mode for sync operations
    mode = data  # "sync" or "overwrite"
    
    # Update message to show processing
    if mode == "sync":
        processing_text = "⏳ <b>Сінхранізацыя...</b>\n\nКалі ласка, пачакайце."
    else:
        processing_text = "⏳ <b>Перазапіс...</b>\n\n⚠️ Усе дадзеныя будуць выдаленыя!\nКалі ласка, пачакайце."
    
    edit_telegram_message(chat_id, message_id, processing_text)
    
    # Trigger GitHub workflow
    success = trigger_github_workflow(mode, chat_id)
    
    if not success:
        error_text = f"❌ <b>Памылка</b>\n\nНе атрымалася запусціць {mode}."
        edit_telegram_message(chat_id, message_id, error_text)
    
    return {"statusCode": 200}


def handle_threshold_input(chat_id: int, user_id: int, text: str, message_id: int) -> Dict[str, Any]:
    """Handle threshold value input from user."""
    try:
        # Parse the input
        threshold = int(text.strip())
        
        # Validate range
        if threshold < 0 or threshold > 100:
            send_telegram_message(
                chat_id,
                "❌ Памылка: лік павінен быць ад 0 да 100.\n\nПаспрабуйце яшчэ раз або выкарыстайце /start для вяртання."
            )
            return {"statusCode": 200}
        
        # Update the setting in database
        success = update_supabase_setting('min_games_threshold', str(threshold))
        
        if success:
            response_text = (
                "✅ <b>Заліковы мінімум зменены!</b>\n\n"
                f"Новае значэнне: <b>{threshold}</b> гульняў\n\n"
                "Змены адразу ж адлюструюцца на сайце.\n\n"
                "Выкарыстайце /start для вяртання ў меню."
            )
        else:
            response_text = (
                "❌ <b>Памылка</b>\n\n"
                "Не атрымалася абнавіць налады.\n\n"
                "Паспрабуйце яшчэ раз ці звяжыцеся з адміністратарам."
            )
        
        send_telegram_message(chat_id, response_text)
        
        # Clear user state
        if user_id in user_states:
            del user_states[user_id]
        
    except ValueError:
        send_telegram_message(
            chat_id,
            "❌ Памылка: увядзіце карэктны лік.\n\nПаспрабуйце яшчэ раз або выкарыстайце /start для вяртання."
        )
    
    return {"statusCode": 200}


def handle_activity_period_input(chat_id: int, user_id: int, text: str, message_id: int) -> Dict[str, Any]:
    """Handle activity period value input from user."""
    try:
        # Parse the input
        period = int(text.strip())
        
        # Validate range
        if period < 1 or period > 365:
            send_telegram_message(
                chat_id,
                "❌ Памылка: лік павінен быць ад 1 да 365.\n\nПаспрабуйце яшчэ раз або выкарыстайце /start для вяртання."
            )
            return {"statusCode": 200}
        
        # Update the setting in database
        success = update_supabase_setting('activity_period_days', str(period))
        
        if success:
            response_text = (
                "✅ <b>Перыяд актыўнасці зменены!</b>\n\n"
                f"Новае значэнне: <b>{period}</b> дзён\n\n"
                "Змены адразу ж адлюструюцца на сайце.\n\n"
                "Выкарыстайце /start для вяртання ў меню."
            )
        else:
            response_text = (
                "❌ <b>Памылка</b>\n\n"
                "Не атрымалася абнавіць налады.\n\n"
                "Паспрабуйце яшчэ раз ці звяжыцеся з адміністратарам."
            )
        
        send_telegram_message(chat_id, response_text)
        
        # Clear user state
        if user_id in user_states:
            del user_states[user_id]
        
    except ValueError:
        send_telegram_message(
            chat_id,
            "❌ Памылка: увядзіце карэктны лік.\n\nПаспрабуйце яшчэ раз або выкарыстайце /start для вяртання."
        )
    
    return {"statusCode": 200}


def handle_hide_player_input(chat_id: int, user_id: int, text: str) -> Dict[str, Any]:
    """Handle hide player name input from user."""
    player_name = text.strip()
    
    if not player_name:
        send_telegram_message(
            chat_id,
            "❌ Памылка: імя гульца не можа быць пустым.\n\nПаспрабуйце яшчэ раз або выкарыстайце /start для вяртання."
        )
        return {"statusCode": 200}
    
    # Get all players to check if player exists
    all_players = get_all_players()
    player_found = None
    
    for player in all_players:
        if player['name'].lower() == player_name.lower():
            player_found = player
            break
    
    if not player_found:
        send_telegram_message(
            chat_id,
            f"❌ <b>Гулец не знойдзены</b>\n\nГулец з імем '<b>{player_name}</b>' не знойдзены ў базе дадзеных.\n\nПраверце правапіс і паспрабуйце яшчэ раз або выкарыстайце /start для вяртання."
        )
        return {"statusCode": 200}
    
    if player_found.get('is_hidden', False):
        send_telegram_message(
            chat_id,
            f"ℹ️ <b>Гулец ужо схаваны</b>\n\nГулец '<b>{player_found['name']}</b>' ужо схаваны.\n\nВыкарыстайце /start для вяртання ў меню."
        )
        # Clear user state
        if user_id in user_states:
            del user_states[user_id]
        return {"statusCode": 200}
    
    # Update player's hidden status
    success = update_player_hidden_status(player_found['name'], True)
    
    if success:
        response_text = (
            f"✅ <b>Гулец схаваны!</b>\n\n"
            f"Гулец '<b>{player_found['name']}</b>' больш не будзе адлюстроўвацца ў галоўнай табліцы па змоўчанні.\n\n"
            "Выкарыстайце /start для вяртання ў меню."
        )
    else:
        response_text = (
            "❌ <b>Памылка</b>\n\n"
            "Не атрымалася абнавіць статус гульца.\n\n"
            "Паспрабуйце яшчэ раз ці звяжыцеся з адміністратарам."
        )
    
    send_telegram_message(chat_id, response_text)
    
    # Clear user state
    if user_id in user_states:
        del user_states[user_id]
    
    return {"statusCode": 200}


def handle_unhide_player_input(chat_id: int, user_id: int, text: str) -> Dict[str, Any]:
    """Handle unhide player name input from user."""
    player_name = text.strip()
    
    if not player_name:
        send_telegram_message(
            chat_id,
            "❌ Памылка: імя гульца не можа быць пустым.\n\nПаспрабуйце яшчэ раз або выкарыстайце /start для вяртання."
        )
        return {"statusCode": 200}
    
    # Get all players to check if player exists
    all_players = get_all_players()
    player_found = None
    
    for player in all_players:
        if player['name'].lower() == player_name.lower():
            player_found = player
            break
    
    if not player_found:
        send_telegram_message(
            chat_id,
            f"❌ <b>Гулец не знойдзены</b>\n\nГулец з імем '<b>{player_name}</b>' не знойдзены ў базе дадзеных.\n\nПраверце правапіс і паспрабуйце яшчэ раз або выкарыстайце /start для вяртання."
        )
        return {"statusCode": 200}
    
    if not player_found.get('is_hidden', False):
        send_telegram_message(
            chat_id,
            f"ℹ️ <b>Гулец ужо адкрыты</b>\n\nГулец '<b>{player_found['name']}</b>' ужо адлюстроўваецца ў табліцы.\n\nВыкарыстайце /start для вяртання ў меню."
        )
        # Clear user state
        if user_id in user_states:
            del user_states[user_id]
        return {"statusCode": 200}
    
    # Update player's hidden status
    success = update_player_hidden_status(player_found['name'], False)
    
    if success:
        response_text = (
            f"✅ <b>Гулец адкрыты!</b>\n\n"
            f"Гулец '<b>{player_found['name']}</b>' цяпер будзе адлюстроўвацца ў галоўнай табліцы.\n\n"
            "Выкарыстайце /start для вяртання ў меню."
        )
    else:
        response_text = (
            "❌ <b>Памылка</b>\n\n"
            "Не атрымалася абнавіць статус гульца.\n\n"
            "Паспрабуйце яшчэ раз ці звяжыцеся з адміністратарам."
        )
    
    send_telegram_message(chat_id, response_text)
    
    # Clear user state
    if user_id in user_states:
        del user_states[user_id]
    
    return {"statusCode": 200}


from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs


class handler(BaseHTTPRequestHandler):
    """
    Vercel entry point using BaseHTTPRequestHandler.
    This is the pattern Vercel's Python runtime expects.
    """
    
    def do_POST(self):
        """Handle POST requests from Telegram webhook."""
        try:
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            body_text = self.rfile.read(content_length).decode('utf-8')
            
            print(f"Received POST request, body length: {content_length}")
            
            # Parse JSON
            try:
                body = json.loads(body_text) if body_text else {}
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}")
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid JSON"}).encode())
                return
            
            print(f"Parsed body keys: {list(body.keys())}")
            
            # Handle different update types
            if "message" in body:
                message = body["message"]
                chat_id = message.get("chat", {}).get("id")
                user_id = message.get("from", {}).get("id")
                text = message.get("text", "")
                message_id = message.get("message_id")
                
                print(f"Message from user {user_id}: {text}")
                
                # Check if user is waiting for input
                if user_id in user_states:
                    waiting_for = user_states[user_id].get("waiting_for")
                    if waiting_for == "threshold":
                        handle_threshold_input(chat_id, user_id, text, message_id)
                    elif waiting_for == "activity_period":
                        handle_activity_period_input(chat_id, user_id, text, message_id)
                    elif waiting_for == "hide_player":
                        handle_hide_player_input(chat_id, user_id, text)
                    elif waiting_for == "unhide_player":
                        handle_unhide_player_input(chat_id, user_id, text)
                elif text.startswith("/start"):
                    handle_start_command(chat_id, user_id)
            
            elif "callback_query" in body:
                print("Handling callback query")
                handle_callback_query(body["callback_query"])
            
            # Always return 200 OK to Telegram
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode())
            
        except Exception as e:
            print(f"Error in handler: {e}")
            import traceback
            traceback.print_exc()
            
            # Still return 200 to Telegram to avoid retries
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode())
    
    def do_GET(self):
        """Reject GET requests."""
        self.send_response(405)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"error": "Method not allowed"}).encode())

