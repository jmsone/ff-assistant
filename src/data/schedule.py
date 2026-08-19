"""NFL schedule + bye weeks from nflverse (free, public).

Source: https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv
Cached to disk to avoid refetching.
"""
from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import requests

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

GAMES_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"

# nflverse -> Sleeper team abbr (nflverse uses LA for Rams; Sleeper uses LAR)
_TEAM_ABBR_FIX = {"LA": "LAR"}

REG_SEASON_MAX_WEEK = 18


def get_games(refresh: bool = False) -> pd.DataFrame:
    """All nflverse games (multi-season). Cached to disk."""
    cache = CACHE_DIR / "nflverse_games.csv"
    if cache.exists() and not refresh:
        return pd.read_csv(cache)
    r = requests.get(GAMES_URL, timeout=30)
    r.raise_for_status()
    cache.write_bytes(r.content)
    return pd.read_csv(io.BytesIO(r.content))


def get_season_schedule(season: int, refresh: bool = False) -> pd.DataFrame:
    """Games for one season, with team abbreviations normalized to Sleeper convention."""
    games = get_games(refresh=refresh)
    df = games[games["season"] == season].copy()
    for col in ("home_team", "away_team"):
        df[col] = df[col].replace(_TEAM_ABBR_FIX)
    return df.reset_index(drop=True)


def get_bye_weeks(season: int, refresh: bool = False) -> dict[str, int]:
    """Team abbr -> bye week number (regular season only)."""
    sched = get_season_schedule(season, refresh=refresh)
    reg = sched[sched["week"] <= REG_SEASON_MAX_WEEK]
    all_weeks = set(range(1, REG_SEASON_MAX_WEEK + 1))
    teams = set(reg["home_team"]) | set(reg["away_team"])
    byes: dict[str, int] = {}
    for team in teams:
        played = set(reg[(reg["home_team"] == team) | (reg["away_team"] == team)]["week"])
        missing = all_weeks - played
        if len(missing) == 1:
            byes[team] = int(next(iter(missing)))
    return byes
