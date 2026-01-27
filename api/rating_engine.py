#!/usr/bin/env python3
"""
Glicko-2 rating engine for Mafia game statistics.
Implements the Glicko-2 rating system to compute player ratings based on game outcomes.

Reference: http://www.glicko.net/glicko/glicko2.pdf
"""

import math
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


# Glicko-2 Constants
INITIAL_RATING = 1500.0
INITIAL_RD = 350.0
INITIAL_SIGMA = 0.06
TAU = 0.5  # System constant (volatility change constraint)
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
    """
    Glicko-2 g function.
    Measures the impact of an opponent's rating deviation.
    """
    return 1.0 / math.sqrt(1.0 + 3.0 * phi * phi / (math.pi * math.pi))


def e_function(mu: float, mu_j: float, phi_j: float) -> float:
    """
    Glicko-2 E function.
    Expected score of player against opponent j.
    """
    return 1.0 / (1.0 + math.exp(-g_function(phi_j) * (mu - mu_j)))


def compute_variance(mu: float, opponents: List[Tuple[float, float]]) -> float:
    """
    Compute the estimated variance of the player's rating based only on game outcomes.
    
    Args:
        mu: Player's rating (Glicko-2 scale)
        opponents: List of (mu_j, phi_j) tuples for each opponent
    
    Returns:
        Estimated variance (v)
    """
    v_inv = 0.0
    for mu_j, phi_j in opponents:
        g = g_function(phi_j)
        e = e_function(mu, mu_j, phi_j)
        v_inv += g * g * e * (1.0 - e)
    
    if v_inv < EPSILON:
        return 1e6  # Very large variance if no games
    
    return 1.0 / v_inv


def compute_delta(mu: float, v: float, opponents: List[Tuple[float, float]], results: List[float]) -> float:
    """
    Compute the improvement in rating based on game outcomes.
    
    Args:
        mu: Player's rating (Glicko-2 scale)
        v: Estimated variance
        opponents: List of (mu_j, phi_j) tuples for each opponent
        results: List of game results (1.0 for win, 0.5 for draw, 0.0 for loss)
    
    Returns:
        Delta value
    """
    delta_sum = 0.0
    for (mu_j, phi_j), s in zip(opponents, results):
        g = g_function(phi_j)
        e = e_function(mu, mu_j, phi_j)
        delta_sum += g * (s - e)
    
    return v * delta_sum


def compute_new_sigma(phi: float, sigma: float, v: float, delta: float) -> float:
    """
    Compute new volatility using Illinois algorithm (iterative method).
    
    Args:
        phi: Player's rating deviation (Glicko-2 scale)
        sigma: Current volatility
        v: Estimated variance
        delta: Rating improvement
    
    Returns:
        New volatility
    """
    # Step 1: Initialize
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
    
    # Step 2: Set initial values
    A = a
    if delta * delta > phi * phi + v:
        B = math.log(delta * delta - phi * phi - v)
    else:
        k = 1
        while f(a - k * TAU) < 0:
            k += 1
        B = a - k * TAU
    
    # Step 3: Iterate to find solution
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


def update_rating(player: PlayerRating, opponents: List[PlayerRating], results: List[float]) -> PlayerRating:
    """
    Update a player's rating based on game results using Glicko-2.
    
    Args:
        player: PlayerRating object for the player
        opponents: List of PlayerRating objects for opponents
        results: List of results (1.0 for win, 0.5 for draw, 0.0 for loss)
    
    Returns:
        New PlayerRating object with updated values
    """
    if not opponents or not results:
        # No games played, just increase RD (rating decay)
        mu, phi = player.to_glicko2_scale()
        phi_star = math.sqrt(phi * phi + player.sigma * player.sigma)
        rating, rd, sigma = PlayerRating.from_glicko2_scale(mu, phi_star, player.sigma)
        return PlayerRating(player.player_id, rating, rd, sigma)
    
    # Convert to Glicko-2 scale
    mu, phi = player.to_glicko2_scale()
    
    # Convert opponents to Glicko-2 scale
    opponent_ratings = [opp.to_glicko2_scale() for opp in opponents]
    
    # Step 3: Compute variance
    v = compute_variance(mu, opponent_ratings)
    
    # Step 4: Compute delta
    delta = compute_delta(mu, v, opponent_ratings, results)
    
    # Step 5: Compute new volatility
    new_sigma = compute_new_sigma(phi, player.sigma, v, delta)
    
    # Step 6: Update rating deviation to new pre-rating period value
    phi_star = math.sqrt(phi * phi + new_sigma * new_sigma)
    
    # Step 7: Update rating and RD to new values
    phi_new = 1.0 / math.sqrt(1.0 / (phi_star * phi_star) + 1.0 / v)
    mu_new = mu + phi_new * phi_new * sum(
        g_function(phi_j) * (s - e_function(mu, mu_j, phi_j))
        for (mu_j, phi_j), s in zip(opponent_ratings, results)
    )
    
    # Convert back to Glicko scale
    rating, rd, sigma = PlayerRating.from_glicko2_scale(mu_new, phi_new, new_sigma)
    
    return PlayerRating(player.player_id, rating, rd, sigma)


def process_game(game_id: int, players_data: List[Tuple[int, bool]], 
                 current_ratings: Dict[int, PlayerRating]) -> Dict[int, Tuple[PlayerRating, PlayerRating]]:
    """
    Process a single game and compute rating changes for all players.
    
    In Mafia, we treat each player as playing against all 10 opponents individually.
    Winners get 1.0 against losers, 0.5 against teammates.
    
    Args:
        game_id: The game ID
        players_data: List of (player_id, won) tuples for all 10 players
        current_ratings: Dict mapping player_id to current PlayerRating
    
    Returns:
        Dict mapping player_id to (rating_before, rating_after) tuples
    """
    if len(players_data) != 10:
        raise ValueError(f"Game {game_id} must have exactly 10 players, got {len(players_data)}")
    
    # Separate winners and losers
    winners = [pid for pid, won in players_data if won]
    losers = [pid for pid, won in players_data if not won]
    
    results = {}
    
    for player_id, player_won in players_data:
        # Get player's current rating (or create new)
        if player_id not in current_ratings:
            current_ratings[player_id] = PlayerRating(player_id)
        
        rating_before = current_ratings[player_id]
        
        # Build opponent list and results
        opponents = []
        game_results = []
        
        for other_id, other_won in players_data:
            if other_id == player_id:
                continue  # Don't play against yourself
            
            # Get opponent's rating
            if other_id not in current_ratings:
                current_ratings[other_id] = PlayerRating(other_id)
            opponents.append(current_ratings[other_id])
            
            # Determine result
            if player_won == other_won:
                # Teammate (same outcome) - draw
                game_results.append(0.5)
            elif player_won:
                # Player won, opponent lost - win
                game_results.append(1.0)
            else:
                # Player lost, opponent won - loss
                game_results.append(0.0)
        
        # Update rating
        rating_after = update_rating(rating_before, opponents, game_results)
        results[player_id] = (rating_before, rating_after)
        
        # Update current ratings for next iteration
        current_ratings[player_id] = rating_after
    
    return results


def full_recompute(api) -> bool:
    """
    Perform full rating recomputation from scratch.
    Deletes all existing ratings and recomputes them for all games in chronological order.
    
    Args:
        api: SupabaseAPI instance
    
    Returns:
        True if successful, False otherwise
    """
    try:
        print("Starting full rating recomputation...")
        
        # Step 1: Delete all existing rating history
        print("Deleting existing rating history...")
        try:
            api.delete('player_rating_history', id='gte.0')
        except Exception:
            pass  # Table might be empty
        
        # Step 2: Get all games in chronological order
        print("Fetching all games...")
        games = api.get('game', select='id,mafia_won', order='id.asc')
        
        if not games:
            print("No games found.")
            return True
        
        print(f"Found {len(games)} games to process.")
        
        # Step 3: Get all game_player records
        print("Fetching game player data...")
        game_players = api.get('game_player', select='game_id,player_id,role_id')
        
        # Step 4: Get role information to determine winners
        roles = api.get('role', select='id,code')
        role_map = {r['id']: r['code'] for r in roles}
        
        # Group by game
        games_data = {}
        for gp in game_players:
            game_id = gp['game_id']
            if game_id not in games_data:
                games_data[game_id] = []
            games_data[game_id].append(gp)
        
        # Step 5: Process each game in order
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
            
            # Determine who won
            players_data = []
            for gp in players_in_game:
                player_id = gp['player_id']
                role_code = role_map[gp['role_id']]
                
                # Determine if this player won
                if role_code in ['M', 'Sh']:  # Citizens/Sheriff
                    won = not mafia_won
                else:  # Mafia/Don
                    won = mafia_won
                
                players_data.append((player_id, won))
            
            # Process the game
            try:
                results = process_game(game_id, players_data, current_ratings)
                
                # Create history records
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
        
        # Step 6: Batch insert rating history
        if rating_history_records:
            print(f"Inserting {len(rating_history_records)} rating history records...")
            # Insert in batches of 100
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


def incremental_compute(api, new_game_ids: List[int]) -> bool:
    """
    Compute ratings incrementally for new games only.
    Uses existing ratings as starting point.
    
    Args:
        api: SupabaseAPI instance
        new_game_ids: List of new game IDs to process
    
    Returns:
        True if successful, False otherwise
    """
    try:
        if not new_game_ids:
            print("No new games to process.")
            return True
        
        print(f"Computing ratings for {len(new_game_ids)} new games...")
        
        # Step 1: Load current ratings for all players
        print("Loading current ratings...")
        current_ratings_data = api.get('player_current_rating', select='player_id,current_rating,current_rd,current_sigma')
        
        current_ratings: Dict[int, PlayerRating] = {}
        for cr in current_ratings_data:
            current_ratings[cr['player_id']] = PlayerRating(
                player_id=cr['player_id'],
                rating=float(cr['current_rating']),
                rd=float(cr['current_rd']),
                sigma=float(cr['current_sigma'])
            )
        
        # Step 2: Get game data for new games
        games = api.get('game', select='id,mafia_won', id=f'in.({",".join(map(str, new_game_ids))})', order='id.asc')
        
        # Step 3: Get game_player records for these games
        game_players = api.get('game_player', select='game_id,player_id,role_id', 
                               game_id=f'in.({",".join(map(str, new_game_ids))})')
        
        # Step 4: Get role information
        roles = api.get('role', select='id,code')
        role_map = {r['id']: r['code'] for r in roles}
        
        # Group by game
        games_data = {}
        for gp in game_players:
            game_id = gp['game_id']
            if game_id not in games_data:
                games_data[game_id] = []
            games_data[game_id].append(gp)
        
        # Step 5: Process each new game
        rating_history_records = []
        
        for game in games:
            game_id = game['id']
            mafia_won = game['mafia_won']
            
            if game_id not in games_data:
                continue
            
            players_in_game = games_data[game_id]
            
            if len(players_in_game) != 10:
                print(f"Warning: Game {game_id} has {len(players_in_game)} players, skipping.")
                continue
            
            # Determine who won
            players_data = []
            for gp in players_in_game:
                player_id = gp['player_id']
                role_code = role_map[gp['role_id']]
                
                # Determine if this player won
                if role_code in ['M', 'Sh']:  # Citizens/Sheriff
                    won = not mafia_won
                else:  # Mafia/Don
                    won = mafia_won
                
                players_data.append((player_id, won))
            
            # Process the game
            try:
                results = process_game(game_id, players_data, current_ratings)
                
                # Create history records
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
        
        # Step 6: Insert rating history
        if rating_history_records:
            print(f"Inserting {len(rating_history_records)} rating history records...")
            api.post('player_rating_history', rating_history_records)
            print("Rating history inserted successfully.")
        
        print(f"Incremental computation complete! Processed {len(games)} games.")
        return True
        
    except Exception as e:
        print(f"Error during incremental computation: {e}")
        import traceback
        traceback.print_exc()
        return False

