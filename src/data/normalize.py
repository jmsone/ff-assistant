"""Normalize FantasyPros projection column names to canonical stat names
matching src/scoring.py expectations.
"""
from __future__ import annotations

import re

import pandas as pd

# Position-specific column mappings.
# FantasyPros multi-header flattening produces names like:
#   QB: passing_att, passing_cmp, passing_yds, passing_tds, passing_ints,
#       rushing_att, rushing_yds, rushing_tds, misc_fl, misc_fpts
#   RB: rushing_att, rushing_yds, rushing_tds, receiving_rec, receiving_yds,
#       receiving_tds, misc_fl, misc_fpts
#   WR: receiving_rec, receiving_yds, receiving_tds, rushing_att, rushing_yds,
#       rushing_tds, misc_fl, misc_fpts
#   TE: receiving_rec, receiving_yds, receiving_tds, misc_fl, misc_fpts
#   K:  fg, fga, xpt, fpts (varies; brackets rare on FantasyPros consensus)
#   DST: sack, int, fr, ff, td, safety, pa, yds_agn, fpts
CANONICAL = {
    "passing_yds": "pass_yd",
    "passing_tds": "pass_td",
    "passing_ints": "pass_int",
    "rushing_yds": "rush_yd",
    "rushing_tds": "rush_td",
    "receiving_rec": "rec",
    "receiving_yds": "rec_yd",
    "receiving_tds": "rec_td",
    "misc_fl": "fumble_lost",
    "misc_fpts": "fpts_fp_default",  # keep FP's default score as reference
    "fpts": "fpts_fp_default",
    # DEF/ST
    "sack": "def_sack",
    "int": "def_int",
    "fr": "def_fumble_rec",
    "ff": "def_ff",  # not scored directly but useful metric
    "td": "def_td",
    "safety": "def_safety",
    # Kicker (FantasyPros consensus doesn't split by yardage bucket)
    "xpt": "xp_made",
}


def _clean_col(c: str) -> str:
    c = re.sub(r"\s+", "_", c.strip().lower())
    c = re.sub(r"[^a-z0-9_]", "", c)
    return c


def _clean_name(name: str) -> str:
    """Strip trailing team abbr from FantasyPros player names, e.g.
    'Ja'Marr Chase CIN' -> 'Ja'Marr Chase'
    """
    if not isinstance(name, str):
        return name
    parts = name.strip().rsplit(" ", 1)
    if len(parts) == 2 and parts[1].isupper() and 2 <= len(parts[1]) <= 3:
        return parts[0]
    return name


def normalize_fantasypros(df: pd.DataFrame) -> pd.DataFrame:
    """Return DataFrame with canonical stat cols + player, position, team."""
    df = df.copy()
    df.columns = [_clean_col(c) for c in df.columns]
    df = df.rename(columns=CANONICAL)

    # Player name column: usually just "player"
    for candidate in ("player", "player_name", "name"):
        if candidate in df.columns:
            df["name_raw"] = df[candidate]
            break

    if "name_raw" in df.columns:
        df["name"] = df["name_raw"].apply(_clean_name)

    # Numeric coercion: everything that's not a name/pos/team
    keep_str = {"name", "name_raw", "position", "team", "player", "player_name"}
    for c in df.columns:
        if c not in keep_str:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    return df
