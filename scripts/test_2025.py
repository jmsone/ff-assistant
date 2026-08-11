"""Test auth against 2025 NFL season (known valid game_id=461).
If this works, auth is fine and 2026 season just isn't live in Yahoo yet.
If this fails, auth/scope is the real problem.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
from dotenv import load_dotenv
from yfpy.query import YahooFantasySportsQuery

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# Try current NFL season data (any league, not yours — public metadata call)
client = YahooFantasySportsQuery(
    league_id="1",  # placeholder; game-level query doesn't require valid league
    game_code="nfl",
    game_id=461,  # 2025 NFL season
    yahoo_consumer_key=os.environ["YAHOO_CONSUMER_KEY"],
    yahoo_consumer_secret=os.environ["YAHOO_CONSUMER_SECRET"],
    env_file_location=ROOT,
    save_token_data_to_env_file=True,
)

try:
    meta = client.get_game_metadata_by_game_id(461)
    print(f"AUTH OK. 2025 NFL game: {meta.name} season={meta.season}")
    print("=> Fantasy scope works. Original error = 2026 season not yet in Yahoo API.")
except Exception as e:
    print(f"FAILED: {e}")
    print("=> Fantasy scope issue at app level. Not a season-timing problem.")
