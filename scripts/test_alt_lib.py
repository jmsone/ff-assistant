"""Test Yahoo Fantasy API access via yahoo-fantasy-api (spilchen) library.
Uses auth/oauth2.json for creds; browser opens for consent on first run.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

ROOT = Path(__file__).resolve().parent.parent
OAUTH_JSON = str(ROOT / "auth" / "oauth2.json")

print("Starting OAuth via yahoo_oauth (yahoo-fantasy-api lib)...")
sc = OAuth2(None, None, from_file=OAUTH_JSON)

if not sc.token_is_valid():
    print("Token invalid/missing. Refreshing...")
    sc.refresh_access_token()

print(f"Access token present: {bool(sc.access_token)}")
print(f"Token valid: {sc.token_is_valid()}\n")

# Try a game-level query
gm = yfa.Game(sc, "nfl")
print(f"Game code: {gm.game_id()}")
print(f"Recent league IDs: {gm.league_ids()[:5]}")
