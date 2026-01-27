#!/usr/bin/env python3
"""
Import Mafia game data from Google Sheets to Supabase via REST API.
Reads CSV from Google Sheets and populates the database with games, players, and results.
This script now uses the sync_engine module for the actual sync logic.
"""

import sys
from api.sync_engine import sync_games


def import_all_games():
    """Main import function."""
    print("=" * 60)
    print("Mafia Game Data Import (via REST API)")
    print("=" * 60)
    
    # Check for --clear flag
    mode = 'overwrite' if ('--clear' in sys.argv or '--force' in sys.argv) else 'sync'
    
    if mode == 'overwrite':
        print("⚠️  Running in CLEAR mode - all existing data will be deleted!")
        print("Press Ctrl+C within 3 seconds to cancel...")
        import time
        time.sleep(3)
    
    # Run the sync
    result = sync_games(mode=mode)
    
    if not result['success']:
        print(f"\n❌ ERROR: {result.get('error', 'Unknown error')}")
        sys.exit(1)
    
    # Display results
    print("\nProcessing games...")
    print("-" * 60)
    
    if mode == 'overwrite':
        print(f"✓ Cleared all existing data")
    
    print(f"✓ Games in spreadsheet: {result['valid_games']} valid, {result['invalid_games']} invalid")
    print(f"✓ Games synced: {result['games_synced']}")
    print(f"✓ Games skipped: {result['games_skipped']}")
    print(f"✓ Players created: {result['players_created']}")
    print(f"✓ Total games in DB: {result['games_in_db_after']}")
    print(f"✓ Total players in DB: {result['players_total']}")
    
    print("-" * 60)
    print(f"\n✓ Import complete!")
    print("=" * 60)


if __name__ == '__main__':
    import_all_games()
