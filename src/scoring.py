"""Apply league scoring rules to raw stat lines → fantasy points."""
from __future__ import annotations

import pandas as pd

from src.config import LeagueConfig

# Canonical stat column names expected on input DataFrames.
# Data sources (Sleeper, FantasyPros, nfl_data_py) must be normalized to these
# before scoring. See src/data/normalize.py.
STAT_COLS = {
    "pass_yd", "pass_td", "pass_int",
    "rush_yd", "rush_td",
    "rec", "rec_yd", "rec_td",
    "fumble_lost", "return_td",
    # Kicker
    "fg_0_19", "fg_20_29", "fg_30_39", "fg_40_49", "fg_50_plus", "xp_made",
    # DEF
    "def_sack", "def_int", "def_fumble_rec", "def_td", "def_safety",
    "def_block", "def_return_td", "def_pa",
}


def _def_pa_points(pa: float, cfg: LeagueConfig) -> float:
    """Points allowed → point value using league brackets."""
    s = cfg.scoring
    if pa <= 0: return s["def_pa_0"]
    if pa <= 6: return s["def_pa_1_6"]
    if pa <= 13: return s["def_pa_7_13"]
    if pa <= 20: return s["def_pa_14_20"]
    if pa <= 27: return s["def_pa_21_27"]
    if pa <= 34: return s["def_pa_28_34"]
    return s["def_pa_35_plus"]


def score_row(row: pd.Series, cfg: LeagueConfig) -> float:
    """Compute fantasy points for a single player-stat row."""
    s = cfg.scoring
    pts = 0.0
    # Offense
    pts += row.get("pass_yd", 0) * s["pass_yd"]
    pts += row.get("pass_td", 0) * s["pass_td"]
    pts += row.get("pass_int", 0) * s["pass_int"]
    pts += row.get("rush_yd", 0) * s["rush_yd"]
    pts += row.get("rush_td", 0) * s["rush_td"]
    pts += row.get("rec", 0) * s["rec"]
    pts += row.get("rec_yd", 0) * s["rec_yd"]
    pts += row.get("rec_td", 0) * s["rec_td"]
    pts += row.get("fumble_lost", 0) * s["fumble_lost"]
    pts += row.get("return_td", 0) * s["return_td"]
    # 2-point conversions
    pts += row.get("pass_2pt", 0) * s.get("pass_2pt", 2)
    pts += row.get("rush_2pt", 0) * s.get("rush_2pt", 2)
    pts += row.get("rec_2pt", 0) * s.get("rec_2pt", 2)
    # Kicker
    pts += row.get("fg_0_19", 0) * s["fg_0_19"]
    pts += row.get("fg_20_29", 0) * s["fg_20_29"]
    pts += row.get("fg_30_39", 0) * s["fg_30_39"]
    pts += row.get("fg_40_49", 0) * s["fg_40_49"]
    pts += row.get("fg_50_plus", 0) * s["fg_50_plus"]
    pts += row.get("xp_made", 0) * s["xp_made"]
    # DEF
    pts += row.get("def_sack", 0) * s["def_sack"]
    pts += row.get("def_int", 0) * s["def_int"]
    pts += row.get("def_fumble_rec", 0) * s["def_fumble_rec"]
    pts += row.get("def_td", 0) * s["def_td"]
    pts += row.get("def_safety", 0) * s["def_safety"]
    pts += row.get("def_block", 0) * s["def_block"]
    pts += row.get("def_return_td", 0) * s["def_return_td"]
    if "def_pa" in row and pd.notna(row["def_pa"]):
        pts += _def_pa_points(row["def_pa"], cfg)
    return pts


def score_dataframe(df: pd.DataFrame, cfg: LeagueConfig, col: str = "fp") -> pd.DataFrame:
    """Add fantasy points column to a projections DataFrame."""
    out = df.copy()
    out[col] = out.apply(lambda r: score_row(r, cfg), axis=1)
    return out
