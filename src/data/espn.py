"""ESPN season projections (free public endpoint).

Endpoint: `lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{season}/segments/0/leaguedefaults/1`

`kona_player_info` view returns per-player projected stats. `appliedTotal` uses ESPN
standard scoring (4pt pass TD, -2 fumble — same as user's league) but no receptions.
We add 0.5 * receptions (stat id 53) to get half-PPR points.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import requests

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

_URL = ("https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{season}"
        "/segments/0/leaguedefaults/1?view=kona_player_info")

_POS_ID = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "DEF"}

# ESPN's proTeamId -> team abbr (aligned with Sleeper convention)
_TEAM_ID = {
    1: "ATL", 2: "BUF", 3: "CHI", 4: "CIN", 5: "CLE", 6: "DAL", 7: "DEN", 8: "DET",
    9: "GB", 10: "TEN", 11: "IND", 12: "KC", 13: "LV", 14: "LAR", 15: "MIA", 16: "MIN",
    17: "NE", 18: "NO", 19: "NYG", 20: "NYJ", 21: "PHI", 22: "ARI", 23: "PIT", 24: "LAC",
    25: "SF", 26: "SEA", 27: "TB", 28: "WAS", 29: "CAR", 30: "JAX", 33: "BAL", 34: "HOU",
}

# ESPN stat IDs used
_REC_ID = "53"


def _fetch(season: int, limit: int = 1000, refresh: bool = False) -> dict:
    cache = CACHE_DIR / f"espn_projections_{season}.json"
    if cache.exists() and not refresh:
        return json.loads(cache.read_text())
    headers = {
        "x-fantasy-filter": json.dumps({
            "players": {
                "limit": limit,
                "sortDraftRanks": {"sortPriority": 100, "sortAsc": True, "value": "STANDARD"},
            }
        }),
        "User-Agent": "Mozilla/5.0",
    }
    r = requests.get(_URL.format(season=season), headers=headers, timeout=45)
    r.raise_for_status()
    data = r.json()
    cache.write_text(json.dumps(data))
    return data


def get_projections(season: int, refresh: bool = False) -> pd.DataFrame:
    """Season projections as half-PPR points.

    Returns cols: espn_id, name, position, team, fp_espn (half-PPR).
    """
    data = _fetch(season, refresh=refresh)
    rows = []
    for pl in data.get("players", []):
        player = pl.get("player") or {}
        pos = _POS_ID.get(player.get("defaultPositionId"))
        if not pos:
            continue
        team = _TEAM_ID.get(player.get("proTeamId"))
        # Find season projection (source=1, splitType=0, period=0)
        applied = None
        rec = 0.0
        for s in player.get("stats", []):
            if (s.get("seasonId") == season
                and s.get("statSourceId") == 1
                and s.get("statSplitTypeId") == 0
                and s.get("scoringPeriodId") == 0):
                applied = s.get("appliedTotal") or 0.0
                rec = (s.get("stats") or {}).get(_REC_ID, 0.0)
                break
        if applied is None:
            continue
        fp_half = float(applied) + 0.5 * float(rec)
        rows.append({
            "espn_id": player.get("id"),
            "name": player.get("fullName"),
            "position": pos,
            "team": team,
            "fp_espn": round(fp_half, 2),
        })
    df = pd.DataFrame(rows)
    return df[df["fp_espn"] > 0].reset_index(drop=True)
