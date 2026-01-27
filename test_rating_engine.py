#!/usr/bin/env python3
"""
Test script for the Glicko-2 rating engine.
This script tests the rating computation with simulated and real game data.
"""

import sys
from rating_engine import (
    PlayerRating, 
    update_rating, 
    process_game,
    g_function,
    e_function,
    INITIAL_RATING,
    INITIAL_RD,
    INITIAL_SIGMA
)


def test_basic_rating_update():
    """Test basic rating update for a simple scenario."""
    print("=" * 60)
    print("Test 1: Basic Rating Update")
    print("=" * 60)
    
    # Create two players
    player1 = PlayerRating(player_id=1, rating=1500, rd=200, sigma=0.06)
    player2 = PlayerRating(player_id=2, rating=1400, rd=30, sigma=0.06)
    
    # Player 1 wins against Player 2
    new_rating = update_rating(player1, [player2], [1.0])
    
    print(f"Player 1 before: Rating={player1.rating:.2f}, RD={player1.rd:.2f}")
    print(f"Player 2: Rating={player2.rating:.2f}, RD={player2.rd:.2f}")
    print(f"Player 1 after win: Rating={new_rating.rating:.2f}, RD={new_rating.rd:.2f}, Sigma={new_rating.sigma:.6f}")
    
    # Verify rating increased
    if new_rating.rating > player1.rating:
        print("✓ Test passed: Rating increased after win")
    else:
        print("✗ Test failed: Rating should increase after win")
        return False
    
    # Verify RD decreased (more games = more certainty)
    if new_rating.rd < player1.rd:
        print("✓ Test passed: RD decreased (more certainty)")
    else:
        print("✗ Test failed: RD should decrease after game")
        return False
    
    print()
    return True


def test_loss_rating_update():
    """Test rating update after a loss."""
    print("=" * 60)
    print("Test 2: Rating Update After Loss")
    print("=" * 60)
    
    # Create two players
    player1 = PlayerRating(player_id=1, rating=1500, rd=200, sigma=0.06)
    player2 = PlayerRating(player_id=2, rating=1600, rd=50, sigma=0.06)
    
    # Player 1 loses against Player 2
    new_rating = update_rating(player1, [player2], [0.0])
    
    print(f"Player 1 before: Rating={player1.rating:.2f}, RD={player1.rd:.2f}")
    print(f"Player 2: Rating={player2.rating:.2f}, RD={player2.rd:.2f}")
    print(f"Player 1 after loss: Rating={new_rating.rating:.2f}, RD={new_rating.rd:.2f}, Sigma={new_rating.sigma:.6f}")
    
    # Verify rating decreased
    if new_rating.rating < player1.rating:
        print("✓ Test passed: Rating decreased after loss")
    else:
        print("✗ Test failed: Rating should decrease after loss")
        return False
    
    print()
    return True


def test_multiple_games():
    """Test rating update over multiple games."""
    print("=" * 60)
    print("Test 3: Multiple Games")
    print("=" * 60)
    
    player = PlayerRating(player_id=1, rating=1500, rd=350, sigma=0.06)
    opponents = [
        PlayerRating(player_id=2, rating=1400, rd=30, sigma=0.06),
        PlayerRating(player_id=3, rating=1550, rd=100, sigma=0.06),
        PlayerRating(player_id=4, rating=1700, rd=300, sigma=0.06),
    ]
    results = [1.0, 0.0, 1.0]  # Win, Loss, Win
    
    print(f"Player before: Rating={player.rating:.2f}, RD={player.rd:.2f}")
    
    new_rating = update_rating(player, opponents, results)
    
    print(f"Player after 3 games: Rating={new_rating.rating:.2f}, RD={new_rating.rd:.2f}, Sigma={new_rating.sigma:.6f}")
    
    # RD should decrease with more games
    if new_rating.rd < player.rd:
        print("✓ Test passed: RD decreased after multiple games")
    else:
        print("✗ Test failed: RD should decrease with more games")
        return False
    
    print()
    return True


def test_team_game():
    """Test 10-player team game processing."""
    print("=" * 60)
    print("Test 4: 10-Player Team Game (Mafia)")
    print("=" * 60)
    
    # Create 10 players (6 citizens win, 4 mafia lose)
    current_ratings = {
        1: PlayerRating(1, 1500, 200, 0.06),
        2: PlayerRating(2, 1500, 200, 0.06),
        3: PlayerRating(3, 1500, 200, 0.06),
        4: PlayerRating(4, 1500, 200, 0.06),
        5: PlayerRating(5, 1500, 200, 0.06),
        6: PlayerRating(6, 1500, 200, 0.06),
        7: PlayerRating(7, 1500, 200, 0.06),
        8: PlayerRating(8, 1500, 200, 0.06),
        9: PlayerRating(9, 1500, 200, 0.06),
        10: PlayerRating(10, 1500, 200, 0.06),
    }
    
    # Citizens (1-6) win, Mafia (7-10) lose
    players_data = [
        (1, True), (2, True), (3, True), (4, True), (5, True), (6, True),  # Winners
        (7, False), (8, False), (9, False), (10, False)  # Losers
    ]
    
    results = process_game(1, players_data, current_ratings)
    
    # Check winner ratings increased
    winner_before = 1500
    winner_after = results[1][1].rating
    print(f"Winner (Player 1): {winner_before:.2f} → {winner_after:.2f}")
    
    # Check loser ratings decreased
    loser_before = 1500
    loser_after = results[7][1].rating
    print(f"Loser (Player 7): {loser_before:.2f} → {loser_after:.2f}")
    
    if winner_after > winner_before:
        print("✓ Test passed: Winner rating increased")
    else:
        print("✗ Test failed: Winner rating should increase")
        return False
    
    if loser_after < loser_before:
        print("✓ Test passed: Loser rating decreased")
    else:
        print("✗ Test failed: Loser rating should decrease")
        return False
    
    print()
    return True


def test_glicko2_functions():
    """Test Glicko-2 mathematical functions."""
    print("=" * 60)
    print("Test 5: Glicko-2 Mathematical Functions")
    print("=" * 60)
    
    # Test g function
    phi = 0.2
    g_val = g_function(phi)
    print(f"g({phi}) = {g_val:.6f}")
    
    if 0 < g_val <= 1:
        print("✓ Test passed: g function returns valid value")
    else:
        print("✗ Test failed: g function should return value in (0, 1]")
        return False
    
    # Test E function (expected score)
    mu1 = 0
    mu2 = 0
    phi2 = 0.2
    e_val = e_function(mu1, mu2, phi2)
    print(f"E({mu1}, {mu2}, {phi2}) = {e_val:.6f}")
    
    # Equal ratings should give 0.5 expected score
    if abs(e_val - 0.5) < 0.01:
        print("✓ Test passed: Equal ratings give ~0.5 expected score")
    else:
        print("✗ Test failed: Equal ratings should give ~0.5 expected score")
        return False
    
    print()
    return True


def test_new_player():
    """Test that new players get default ratings."""
    print("=" * 60)
    print("Test 6: New Player Default Ratings")
    print("=" * 60)
    
    new_player = PlayerRating(player_id=999)
    
    print(f"New player: Rating={new_player.rating}, RD={new_player.rd}, Sigma={new_player.sigma}")
    
    if (new_player.rating == INITIAL_RATING and 
        new_player.rd == INITIAL_RD and 
        new_player.sigma == INITIAL_SIGMA):
        print("✓ Test passed: New player has correct default ratings")
    else:
        print("✗ Test failed: New player should have default ratings")
        return False
    
    print()
    return True


def main():
    """Run all tests."""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "GLICKO-2 RATING ENGINE TEST SUITE" + " " * 15 + "║")
    print("╚" + "=" * 58 + "╝")
    print()
    
    tests = [
        test_glicko2_functions,
        test_new_player,
        test_basic_rating_update,
        test_loss_rating_update,
        test_multiple_games,
        test_team_game,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Total tests: {passed + failed}")
    print(f"✓ Passed: {passed}")
    print(f"✗ Failed: {failed}")
    print("=" * 60)
    
    if failed == 0:
        print("\n🎉 All tests passed! Rating engine is working correctly.")
        return 0
    else:
        print(f"\n❌ {failed} test(s) failed. Please review the output above.")
        return 1


if __name__ == '__main__':
    sys.exit(main())

