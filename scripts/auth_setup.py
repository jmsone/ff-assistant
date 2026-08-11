"""Run once to complete Yahoo OAuth flow.

Opens browser, prompts for verifier code, saves refresh token to .env.
After this, all future scripts auth silently via refresh token.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.yahoo_client import get_client


def main() -> None:
    print("Starting Yahoo OAuth flow...")
    print("Browser will open. Sign in, approve, copy verifier code, paste back here.\n")

    client = get_client()

    # Trigger a trivial API call to force token exchange
    league = client.get_league_info()
    print(f"\nAuth OK. League: {league.name} ({league.num_teams} teams, {league.season})")
    print("Refresh token saved to .env. You will not need to re-auth.")


if __name__ == "__main__":
    main()
