"""Playoff Strength-of-Schedule grading.

Uses prior-season (2025) fantasy points allowed per team per position to grade
each 2026 player's playoff matchups (weeks 16-17 by league config).

Grade is a TIEBREAKER column — never baked into VBD. Per user guardrail:
straight ROS projection wins at draft time; playoff schedule only breaks ties
within the same tier.
"""
from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import requests

from src.data.schedule import get_season_schedule

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

_STATS_URL = "https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{season}.csv"
_TEAM_ABBR_FIX = {"LA": "LAR"}

SCORING_POSITIONS = ("QB", "RB", "WR", "TE")
REG_WEEKS = 18


def _fetch_player_weekly(season: int, refresh: bool = False) -> pd.DataFrame:
    cache = CACHE_DIR / f"nflverse_player_stats_{season}.csv"
    if cache.exists() and not refresh:
        return pd.read_csv(cache, low_memory=False)
    r = requests.get(_STATS_URL.format(season=season), timeout=90)
    r.raise_for_status()
    cache.write_bytes(r.content)
    return pd.read_csv(io.BytesIO(r.content), low_memory=False)


def compute_dvp_ratio(prior_season: int, refresh: bool = False) -> pd.DataFrame:
    """FP-allowed ratio (team defense vs position) from `prior_season`.

    Returns DataFrame indexed by opponent team abbr with cols QB/RB/WR/TE.
    Value = (team FP allowed / game to pos) / (league avg FP allowed / game to pos).
    >1.0 = softer than average (easier matchup). <1.0 = tougher.
    """
    df = _fetch_player_weekly(prior_season, refresh=refresh)
    df = df[(df["season_type"] == "REG") & df["position"].isin(SCORING_POSITIONS)].copy()
    for col in ("team", "opponent_team"):
        df[col] = df[col].replace(_TEAM_ABBR_FIX)

    # Half-PPR proxy: mean of nflverse std + ppr (they differ only in receptions)
    df["fp_half"] = (df["fantasy_points"].fillna(0) + df["fantasy_points_ppr"].fillna(0)) / 2

    # FP allowed by each defense to each position per week
    allowed = (
        df.groupby(["opponent_team", "position", "week"], as_index=False)["fp_half"].sum()
    )
    # Season avg per team per position (mean over weeks the team played)
    team_avg = (
        allowed.groupby(["opponent_team", "position"], as_index=False)["fp_half"].mean()
        .pivot(index="opponent_team", columns="position", values="fp_half")
    )
    # Normalize each column to its league mean
    ratio = team_avg / team_avg.mean(axis=0)
    return ratio


def _grade(ratio: float) -> str:
    """Ratio → letter grade. Higher ratio = easier matchup = better grade."""
    if pd.isna(ratio):
        return ""
    if ratio >= 1.10:
        return "A"
    if ratio >= 1.03:
        return "B"
    if ratio >= 0.97:
        return "C"
    if ratio >= 0.90:
        return "D"
    return "F"


def playoff_opponents(target_season: int, weeks: tuple[int, ...] = (16, 17),
                      refresh: bool = False) -> dict[str, list[str]]:
    """Team abbr -> list of opponents for the given weeks (in week order)."""
    sched = get_season_schedule(target_season, refresh=refresh)
    sched = sched[sched["week"].isin(weeks)].copy()
    result: dict[str, list[tuple[int, str]]] = {}
    for _, row in sched.iterrows():
        home, away, wk = row["home_team"], row["away_team"], int(row["week"])
        result.setdefault(home, []).append((wk, away))
        result.setdefault(away, []).append((wk, home))
    return {t: [opp for _, opp in sorted(games)] for t, games in result.items()}


def playoff_sos_grades(
    target_season: int,
    prior_season: int,
    weeks: tuple[int, ...] = (16, 17),
    refresh: bool = False,
) -> pd.DataFrame:
    """Per-(team, position) playoff SoS.

    Returns long DataFrame: team, position, sos_ratio, sos_grade, sos_opps.
    `sos_ratio` = mean of prior-season DvP ratios across `weeks` opponents.
    """
    ratio = compute_dvp_ratio(prior_season, refresh=refresh)
    opps_by_team = playoff_opponents(target_season, weeks=weeks, refresh=refresh)

    rows = []
    for team, opps in opps_by_team.items():
        opps_str = " > ".join(opps)
        for pos in SCORING_POSITIONS:
            vals = [ratio.at[o, pos] for o in opps if o in ratio.index and pos in ratio.columns]
            avg = float(sum(vals) / len(vals)) if vals else float("nan")
            rows.append({
                "team": team,
                "position": pos,
                "sos_ratio": avg,
                "sos_grade": _grade(avg),
                "sos_opps": opps_str,
            })
    return pd.DataFrame(rows)
