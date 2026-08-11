"""Yahoo Fantasy Sports API client wrapper."""
import os
from pathlib import Path

from dotenv import load_dotenv
from yfpy.query import YahooFantasySportsQuery

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"

# NFL game IDs by season. Update yearly.
# Find current via: https://api-football.com/... or yfpy get_all_yahoo_fantasy_game_keys
GAME_ID_BY_SEASON = {
    2024: 449,
    2025: 461,
    2026: None,  # unknown until season opens; leave None to auto-resolve
}


def get_client(league_id: str | None = None, season: int | None = None) -> YahooFantasySportsQuery:
    load_dotenv(ENV_PATH)

    league_id = league_id or os.environ["YAHOO_LEAGUE_ID"]
    season = season or int(os.environ.get("YAHOO_SEASON", 2026))
    game_code = os.environ.get("YAHOO_GAME_CODE", "nfl")
    game_id = GAME_ID_BY_SEASON.get(season)

    return YahooFantasySportsQuery(
        league_id=league_id,
        game_code=game_code,
        game_id=game_id,
        yahoo_consumer_key=os.environ["YAHOO_CONSUMER_KEY"],
        yahoo_consumer_secret=os.environ["YAHOO_CONSUMER_SECRET"],
        env_file_location=PROJECT_ROOT,
        save_token_data_to_env_file=True,
    )
