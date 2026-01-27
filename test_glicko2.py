#!/usr/bin/env python3
"""
Test script for Glicko-2 rating system.
Creates a simulated 10-player Mafia game and shows rating changes.
"""

import math
from typing import Dict, List, Tuple
from dataclasses import dataclass

# Copy of the Glicko-2 implementation from telegram_webhook.py
INITIAL_RATING = 1500.0
INITIAL_RD = 350.0
INITIAL_SIGMA = 0.06
TAU = 0.5
EPSILON = 0.000001


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


def compute_variance(mu: float, opponents: List[Tuple[float, float]]) -> float:
    """Compute the estimated variance of the player's rating."""
    v_inv = 0.0
    for mu_j, phi_j in opponents:
        g = g_function(phi_j)
        e = e_function(mu, mu_j, phi_j)
        v_inv += g * g * e * (1.0 - e)
    
    if v_inv < EPSILON:
        return 1e6
    
    return 1.0 / v_inv


def compute_delta(mu: float, v: float, opponents: List[Tuple[float, float]], results: List[float]) -> float:
    """Compute the improvement in rating based on game outcomes."""
    delta_sum = 0.0
    for (mu_j, phi_j), s in zip(opponents, results):
        g = g_function(phi_j)
        e = e_function(mu, mu_j, phi_j)
        delta_sum += g * (s - e)
    
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


def update_rating(player: PlayerRating, opponents: List[PlayerRating], results: List[float]) -> PlayerRating:
    """Update a player's rating based on game results using Glicko-2."""
    if not opponents or not results:
        mu, phi = player.to_glicko2_scale()
        phi_star = math.sqrt(phi * phi + player.sigma * player.sigma)
        rating, rd, sigma = PlayerRating.from_glicko2_scale(mu, phi_star, player.sigma)
        return PlayerRating(player.player_id, rating, rd, sigma)
    
    mu, phi = player.to_glicko2_scale()
    opponent_ratings = [opp.to_glicko2_scale() for opp in opponents]
    
    v = compute_variance(mu, opponent_ratings)
    delta = compute_delta(mu, v, opponent_ratings, results)
    new_sigma = compute_new_sigma(phi, player.sigma, v, delta)
    phi_star = math.sqrt(phi * phi + new_sigma * new_sigma)
    phi_new = 1.0 / math.sqrt(1.0 / (phi_star * phi_star) + 1.0 / v)
    mu_new = mu + phi_new * phi_new * sum(
        g_function(phi_j) * (s - e_function(mu, mu_j, phi_j))
        for (mu_j, phi_j), s in zip(opponent_ratings, results)
    )
    
    rating, rd, sigma = PlayerRating.from_glicko2_scale(mu_new, phi_new, new_sigma)
    return PlayerRating(player.player_id, rating, rd, sigma)


def process_game(game_id: int, players_data: List[Tuple[int, bool]], 
                 current_ratings: Dict[int, PlayerRating]) -> Dict[int, Tuple[PlayerRating, PlayerRating]]:
    """Process a single game and compute rating changes for all players."""
    if len(players_data) != 10:
        raise ValueError(f"Game {game_id} must have exactly 10 players, got {len(players_data)}")
    
    results = {}
    
    for player_id, player_won in players_data:
        if player_id not in current_ratings:
            current_ratings[player_id] = PlayerRating(player_id)
        
        rating_before = current_ratings[player_id]
        opponents = []
        game_results = []
        
        for other_id, other_won in players_data:
            if other_id == player_id:
                continue
            
            if other_id not in current_ratings:
                current_ratings[other_id] = PlayerRating(other_id)
            opponents.append(current_ratings[other_id])
            
            if player_won == other_won:
                game_results.append(0.5)
            elif player_won:
                game_results.append(1.0)
            else:
                game_results.append(0.0)
        
        rating_after = update_rating(rating_before, opponents, game_results)
        results[player_id] = (rating_before, rating_after)
        current_ratings[player_id] = rating_after
    
    return results


def print_separator():
    print("=" * 80)


def test_scenario_1_all_new_players():
    """Test 1: All players start with default rating (1500)."""
    print_separator()
    print("TEST 1: All 10 players are new (rating 1500), Citizens win")
    print_separator()
    
    current_ratings = {}
    
    # 8 citizens (won), 2 mafia (lost)
    players_data = [
        (1, True),   # Citizen
        (2, True),   # Citizen
        (3, True),   # Citizen
        (4, True),   # Citizen
        (5, True),   # Citizen
        (6, True),   # Citizen
        (7, True),   # Citizen
        (8, True),   # Citizen (Sheriff)
        (9, False),  # Mafia
        (10, False), # Mafia (Don)
    ]
    
    results = process_game(1, players_data, current_ratings)
    
    print("\nResults:")
    print(f"{'Player':<10} {'Before':<15} {'After':<15} {'Change':<10} {'RD Change':<12}")
    print("-" * 80)
    
    for pid in range(1, 11):
        before, after = results[pid]
        rating_change = after.rating - before.rating
        rd_change = after.rd - before.rd
        won = players_data[pid-1][1]
        status = "WON" if won else "LOST"
        
        print(f"P{pid:<9} {before.rating:<15.2f} {after.rating:<15.2f} {rating_change:+10.2f} {rd_change:+12.2f}  {status}")
    
    print(f"\nAverage rating change for winners: {sum(results[i][1].rating - results[i][0].rating for i in range(1, 9)) / 8:.2f}")
    print(f"Average rating change for losers:  {sum(results[i][1].rating - results[i][0].rating for i in range(9, 11)) / 2:.2f}")


def test_scenario_2_mixed_ratings():
    """Test 2: Players with different ratings."""
    print_separator()
    print("TEST 2: Mixed ratings - strong players vs weak players, underdogs win")
    print_separator()
    
    current_ratings = {
        # Strong citizens (but they lose)
        1: PlayerRating(1, rating=1800, rd=80),
        2: PlayerRating(2, rating=1750, rd=90),
        3: PlayerRating(3, rating=1700, rd=85),
        4: PlayerRating(4, rating=1650, rd=95),
        5: PlayerRating(5, rating=1600, rd=100),
        6: PlayerRating(6, rating=1550, rd=110),
        # Weak mafia (but they win!)
        7: PlayerRating(7, rating=1300, rd=120),
        8: PlayerRating(8, rating=1250, rd=130),
        9: PlayerRating(9, rating=1200, rd=140),
        10: PlayerRating(10, rating=1150, rd=150),
    }
    
    # Mafia wins (upset!)
    players_data = [
        (1, False),  # Citizen - lost
        (2, False),  # Citizen - lost
        (3, False),  # Citizen - lost
        (4, False),  # Citizen - lost
        (5, False),  # Citizen - lost
        (6, False),  # Citizen - lost
        (7, True),   # Mafia - won
        (8, True),   # Mafia - won
        (9, True),   # Mafia - won
        (10, True),  # Mafia (Don) - won
    ]
    
    results = process_game(2, players_data, current_ratings)
    
    print("\nResults:")
    print(f"{'Player':<10} {'Before':<15} {'After':<15} {'Change':<10} {'Status':<10}")
    print("-" * 80)
    
    for pid in range(1, 11):
        before, after = results[pid]
        rating_change = after.rating - before.rating
        won = players_data[pid-1][1]
        status = "WON" if won else "LOST"
        role = "Mafia" if pid >= 7 else "Citizen"
        
        print(f"P{pid} ({role:<6}) {before.rating:<15.2f} {after.rating:<15.2f} {rating_change:+10.2f} {status}")
    
    print(f"\nNote: Weak mafia gained a LOT for beating strong citizens (upset victory)")
    print(f"      Strong citizens lost a LOT for losing to weak mafia")


def test_scenario_3_multiple_games():
    """Test 3: Track a player through multiple games."""
    print_separator()
    print("TEST 3: Track Player 1 through 5 games (3 wins, 2 losses)")
    print_separator()
    
    current_ratings = {}
    
    games = [
        # Game 1: Player 1 wins
        [(1, True), (2, True), (3, True), (4, True), (5, True), (6, True), 
         (7, False), (8, False), (9, False), (10, False)],
        # Game 2: Player 1 wins
        [(1, True), (11, True), (12, True), (13, True), (14, True), (15, True),
         (16, False), (17, False), (18, False), (19, False)],
        # Game 3: Player 1 loses
        [(1, False), (20, False), (21, False), (22, False), (23, False), (24, False),
         (25, True), (26, True), (27, True), (28, True)],
        # Game 4: Player 1 wins
        [(1, True), (29, True), (30, True), (31, True), (32, True), (33, True),
         (34, False), (35, False), (36, False), (37, False)],
        # Game 5: Player 1 loses
        [(1, False), (38, False), (39, False), (40, False), (41, False), (42, False),
         (43, True), (44, True), (45, True), (46, True)],
    ]
    
    print(f"\n{'Game':<6} {'Before':<15} {'After':<15} {'Change':<10} {'RD':<12} {'Result'}")
    print("-" * 80)
    
    for game_num, players_data in enumerate(games, 1):
        results = process_game(game_num, players_data, current_ratings)
        before, after = results[1]
        change = after.rating - before.rating
        won = players_data[0][1]
        result = "WIN" if won else "LOSS"
        
        print(f"{game_num:<6} {before.rating:<15.2f} {after.rating:<15.2f} {change:+10.2f} {after.rd:<12.2f} {result}")
    
    print(f"\nFinal rating: {current_ratings[1].rating:.2f}")
    print(f"Rating change from initial: {current_ratings[1].rating - 1500:.2f}")
    print(f"Final RD (uncertainty): {current_ratings[1].rd:.2f} (started at {INITIAL_RD})")


if __name__ == "__main__":
    print("\n🎮 GLICKO-2 RATING SYSTEM TEST SUITE")
    print("Testing Mafia game rating calculations\n")
    
    test_scenario_1_all_new_players()
    print("\n\n")
    test_scenario_2_mixed_ratings()
    print("\n\n")
    test_scenario_3_multiple_games()
    
    print("\n" + "=" * 80)
    print("✅ All tests completed!")
    print("=" * 80)

