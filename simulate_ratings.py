#!/usr/bin/env python3
"""
Simulation script to test Glicko-2 rating behavior in various scenarios.
"""

import math
import random
from typing import Dict, List, Tuple
from dataclasses import dataclass

# Copy Glicko-2 implementation
INITIAL_RATING = 1500.0
INITIAL_RD = 350.0
INITIAL_SIGMA = 0.06
TAU = 0.5
EPSILON = 0.000001


@dataclass
class PlayerRating:
    player_id: int
    rating: float = INITIAL_RATING
    rd: float = INITIAL_RD
    sigma: float = INITIAL_SIGMA
    games_as_red: int = 0
    games_as_black: int = 0
    wins: int = 0
    losses: int = 0
    
    def to_glicko2_scale(self) -> Tuple[float, float]:
        mu = (self.rating - 1500) / 173.7178
        phi = self.rd / 173.7178
        return mu, phi
    
    @staticmethod
    def from_glicko2_scale(mu: float, phi: float, sigma: float) -> Tuple[float, float, float]:
        rating = mu * 173.7178 + 1500
        rd = phi * 173.7178
        return rating, rd, sigma


def g_function(phi: float) -> float:
    return 1.0 / math.sqrt(1.0 + 3.0 * phi * phi / (math.pi * math.pi))


def e_function(mu: float, mu_j: float, phi_j: float) -> float:
    return 1.0 / (1.0 + math.exp(-g_function(phi_j) * (mu - mu_j)))


def compute_variance(mu: float, opponents: List[Tuple[float, float]]) -> float:
    v_inv = 0.0
    for mu_j, phi_j in opponents:
        g = g_function(phi_j)
        e = e_function(mu, mu_j, phi_j)
        v_inv += g * g * e * (1.0 - e)
    
    if v_inv < EPSILON:
        return 1e6
    
    return 1.0 / v_inv


def compute_delta(mu: float, v: float, opponents: List[Tuple[float, float]], results: List[float]) -> float:
    delta_sum = 0.0
    for (mu_j, phi_j), s in zip(opponents, results):
        g = g_function(phi_j)
        e = e_function(mu, mu_j, phi_j)
        delta_sum += g * (s - e)
    
    return v * delta_sum


def compute_new_sigma(phi: float, sigma: float, v: float, delta: float) -> float:
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
    return PlayerRating(player.player_id, rating, rd, sigma, 
                        player.games_as_red, player.games_as_black,
                        player.wins, player.losses)


def process_game(players_data: List[Tuple[int, bool]], 
                 current_ratings: Dict[int, PlayerRating]) -> Dict[int, PlayerRating]:
    """Process game with micromatch approach - only opposing teams play."""
    
    for player_id, player_won in players_data:
        if player_id not in current_ratings:
            current_ratings[player_id] = PlayerRating(player_id)
        
        rating_before = current_ratings[player_id]
        opponents = []
        game_results = []
        
        # Count team sizes
        red_team = [pid for pid, won in players_data if won]
        black_team = [pid for pid, won in players_data if not won]
        
        # Track role assignment
        if player_won:
            current_ratings[player_id].games_as_red += 1
        else:
            current_ratings[player_id].games_as_black += 1
        
        for other_id, other_won in players_data:
            if other_id == player_id:
                continue
            
            # Only match against opposing team
            if player_won == other_won:
                continue
            
            if other_id not in current_ratings:
                current_ratings[other_id] = PlayerRating(other_id)
            opponents.append(current_ratings[other_id])
            
            if player_won:
                game_results.append(1.0)
            else:
                game_results.append(0.0)
        
        # Update win/loss counts
        if player_won:
            current_ratings[player_id].wins += 1
        else:
            current_ratings[player_id].losses += 1
        
        rating_after = update_rating(rating_before, opponents, game_results)
        rating_after.games_as_red = current_ratings[player_id].games_as_red
        rating_after.games_as_black = current_ratings[player_id].games_as_black
        rating_after.wins = current_ratings[player_id].wins
        rating_after.losses = current_ratings[player_id].losses
        current_ratings[player_id] = rating_after
    
    return current_ratings


def simulation_1_balanced_play():
    """
    Simulation 1: 10 players, each wins ~50% of games randomly.
    Expected: All ratings converge near 1500.
    """
    print("=" * 80)
    print("SIMULATION 1: Balanced Play (Random 50/50 wins)")
    print("=" * 80)
    print("\nScenario: 10 players play 100 games with random outcomes (50% red win rate)")
    print("Expected: All ratings should converge near 1500\n")
    
    current_ratings = {}
    num_games = 100
    
    # Play 100 games with random outcomes
    for game_num in range(1, num_games + 1):
        # Random team assignment (7 red, 3 black)
        all_players = list(range(1, 11))
        random.shuffle(all_players)
        red_team = all_players[:7]
        black_team = all_players[7:]
        
        # Random winner (50% chance each)
        red_wins = random.random() < 0.5
        
        players_data = [(pid, red_wins) for pid in red_team] + [(pid, not red_wins) for pid in black_team]
        
        process_game(players_data, current_ratings)
    
    # Print results
    print(f"After {num_games} games:\n")
    print(f"{'Player':<10} {'Rating':<10} {'RD':<10} {'W-L':<10} {'Red%':<10} {'Black%':<10}")
    print("-" * 70)
    
    ratings_list = []
    for pid in range(1, 11):
        player = current_ratings[pid]
        total_games = player.wins + player.losses
        red_pct = (player.games_as_red / total_games * 100) if total_games > 0 else 0
        black_pct = (player.games_as_black / total_games * 100) if total_games > 0 else 0
        ratings_list.append(player.rating)
        print(f"P{pid:<9} {player.rating:<10.1f} {player.rd:<10.1f} "
              f"{player.wins}-{player.losses:<8} {red_pct:<10.1f} {black_pct:<10.1f}")
    
    avg_rating = sum(ratings_list) / len(ratings_list)
    std_dev = (sum((r - avg_rating) ** 2 for r in ratings_list) / len(ratings_list)) ** 0.5
    
    print(f"\n{'Average rating:':<20} {avg_rating:.1f}")
    print(f"{'Standard deviation:':<20} {std_dev:.1f}")
    print(f"{'Range:':<20} {min(ratings_list):.1f} - {max(ratings_list):.1f}")
    
    print("\n✅ Result: Ratings should be close to 1500 with small variance")


def simulation_2_asymmetry_fairness():
    """
    Simulation 2: Same 10 players, but track rating changes by team.
    Test if the 7vs3 asymmetry is fair over many games.
    """
    print("\n\n" + "=" * 80)
    print("SIMULATION 2: Team Asymmetry Fairness")
    print("=" * 80)
    print("\nScenario: Track how rating changes differ between Red (7) vs Black (3) roles")
    print("Expected: Over many games with random roles, average gains should balance out\n")
    
    current_ratings = {}
    num_games = 200
    
    red_wins_list = []
    red_losses_list = []
    black_wins_list = []
    black_losses_list = []
    
    # Play 200 games
    for game_num in range(1, num_games + 1):
        all_players = list(range(1, 11))
        random.shuffle(all_players)
        red_team = all_players[:7]
        black_team = all_players[7:]
        
        red_wins = random.random() < 0.5
        
        # Save ratings before
        before_ratings = {pid: current_ratings[pid].rating if pid in current_ratings else 1500.0 
                         for pid in all_players}
        
        players_data = [(pid, red_wins) for pid in red_team] + [(pid, not red_wins) for pid in black_team]
        process_game(players_data, current_ratings)
        
        # Track rating changes by role and outcome
        for pid in red_team:
            change = current_ratings[pid].rating - before_ratings[pid]
            if red_wins:
                red_wins_list.append(change)
            else:
                red_losses_list.append(change)
        
        for pid in black_team:
            change = current_ratings[pid].rating - before_ratings[pid]
            if not red_wins:  # black wins
                black_wins_list.append(change)
            else:  # black losses
                black_losses_list.append(change)
    
    # Print results
    print(f"After {num_games} games:\n")
    print(f"{'Scenario':<30} {'Avg Change':<15} {'Sample Size':<15}")
    print("-" * 60)
    print(f"{'Red team wins:':<30} {sum(red_wins_list)/len(red_wins_list):+.2f} points     "
          f"{len(red_wins_list)} samples")
    print(f"{'Red team loses:':<30} {sum(red_losses_list)/len(red_losses_list):+.2f} points     "
          f"{len(red_losses_list)} samples")
    print(f"{'Black team wins:':<30} {sum(black_wins_list)/len(black_wins_list):+.2f} points     "
          f"{len(black_wins_list)} samples")
    print(f"{'Black team loses:':<30} {sum(black_losses_list)/len(black_losses_list):+.2f} points     "
          f"{len(black_losses_list)} samples")
    
    # Calculate expected value per player
    red_expected = (sum(red_wins_list) + sum(red_losses_list)) / (len(red_wins_list) + len(red_losses_list))
    black_expected = (sum(black_wins_list) + sum(black_losses_list)) / (len(black_wins_list) + len(black_losses_list))
    
    print(f"\n{'Expected value per game:':<30}")
    print(f"  {'Playing as Red:':<28} {red_expected:+.2f} points")
    print(f"  {'Playing as Black:':<28} {black_expected:+.2f} points")
    
    # Check balance per player (weighted by role frequency: ~70% red, ~30% black)
    overall_expected = red_expected * 0.7 + black_expected * 0.3
    print(f"\n{'Weighted average (70% red, 30% black):':<40} {overall_expected:+.2f} points")
    
    print("\n✅ Result: The system is fair if weighted average ≈ 0")
    print("   (Positive/negative shifts cancel out over many games)")


def simulation_3_skill_levels():
    """
    Simulation 3: Players with different true skill levels.
    3 strong players (win 70%), 4 average (50%), 3 weak (30%)
    """
    print("\n\n" + "=" * 80)
    print("SIMULATION 3: Different Skill Levels")
    print("=" * 80)
    print("\nScenario: 3 strong (70% win), 4 average (50%), 3 weak (30%)")
    print("Expected: Ratings separate into tiers\n")
    
    current_ratings = {}
    num_games = 150
    
    # Define player skill levels (win probability boost)
    player_skills = {
        1: 0.7, 2: 0.7, 3: 0.7,  # Strong
        4: 0.5, 5: 0.5, 6: 0.5, 7: 0.5,  # Average
        8: 0.3, 9: 0.3, 10: 0.3  # Weak
    }
    
    for game_num in range(1, num_games + 1):
        all_players = list(range(1, 11))
        random.shuffle(all_players)
        red_team = all_players[:7]
        black_team = all_players[7:]
        
        # Calculate team strength (average win probability)
        red_strength = sum(player_skills[pid] for pid in red_team) / len(red_team)
        black_strength = sum(player_skills[pid] for pid in black_team) / len(black_team)
        
        # Winner determined by relative strength
        total_strength = red_strength + black_strength
        red_wins = random.random() < (red_strength / total_strength)
        
        players_data = [(pid, red_wins) for pid in red_team] + [(pid, not red_wins) for pid in black_team]
        process_game(players_data, current_ratings)
    
    # Print results
    print(f"After {num_games} games:\n")
    print(f"{'Player':<10} {'Skill':<10} {'Rating':<10} {'RD':<10} {'W-L':<10} {'Win%':<10}")
    print("-" * 70)
    
    for pid in range(1, 11):
        player = current_ratings[pid]
        total_games = player.wins + player.losses
        win_pct = (player.wins / total_games * 100) if total_games > 0 else 0
        skill = player_skills[pid]
        skill_label = "Strong" if skill == 0.7 else ("Weak" if skill == 0.3 else "Average")
        print(f"P{pid:<9} {skill_label:<10} {player.rating:<10.1f} {player.rd:<10.1f} "
              f"{player.wins}-{player.losses:<8} {win_pct:.1f}%")
    
    print("\n✅ Result: Strong players should have ratings ~1600-1700")
    print("           Average players should stay near ~1500")
    print("           Weak players should drop to ~1300-1400")


if __name__ == "__main__":
    random.seed(42)  # For reproducibility
    
    print("\n" + "=" * 80)
    print(" " * 20 + "GLICKO-2 RATING SIMULATIONS")
    print("=" * 80)
    
    simulation_1_balanced_play()
    simulation_2_asymmetry_fairness()
    simulation_3_skill_levels()
    
    print("\n" + "=" * 80)
    print("SIMULATIONS COMPLETE")
    print("=" * 80 + "\n")

