"""Sleeper API client. Free, no auth. Docs: https://docs.sleeper.com/"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import requests

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

BASE = "https://api.sleeper.app/v1"

# Sleeper stat field -> canonical scoring field
STAT_MAP = {
    "pass_yd": "pass_yd",
    "pass_td": "pass_td",
    "pass_int": "pass_int",
    "pass_2pt": "pass_2pt",
    "rush_yd": "rush_yd",
    "rush_td": "rush_td",
    "rush_2pt": "rush_2pt",
    "rec": "rec",
    "rec_yd": "rec_yd",
    "rec_td": "rec_td",
    "rec_2pt": "rec_2pt",
    "fum_lost": "fumble_lost",
}


def get_all_players(refresh: bool = False) -> pd.DataFrame:
    """All NFL players. ~5MB response; cached to disk."""
    cache = CACHE_DIR / "sleeper_players.json"
    if cache.exists() and not refresh:
        raw = json.loads(cache.read_text())
    else:
        r = requests.get(f"{BASE}/players/nfl", timeout=30)
        r.raise_for_status()
        raw = r.json()
        cache.write_text(json.dumps(raw))

    rows = []
    for pid, p in raw.items():
        rows.append({
            "sleeper_id": pid,
            "name": p.get("full_name") or f"{p.get('first_name','')} {p.get('last_name','')}".strip(),
            "position": p.get("position"),
            "team": p.get("team"),
            "age": p.get("age"),
            "years_exp": p.get("years_exp"),
            "status": p.get("status"),
            "injury_status": p.get("injury_status"),
            "depth_chart_order": p.get("depth_chart_order"),
            "college": p.get("college"),
        })
    df = pd.DataFrame(rows)
    df = df[df["position"].isin(["QB", "RB", "WR", "TE", "K", "DEF"])]
    df = df[df["team"].notna()]
    return df.reset_index(drop=True)


def get_season_projections(season: int) -> pd.DataFrame:
    """Full-season projections for all players. Includes multi-format ADP.
    Returns wide DataFrame: sleeper_id, all stat fields, adp_*.
    """
    r = requests.get(f"{BASE}/projections/nfl/regular/{season}", timeout=30)
    r.raise_for_status()
    raw = r.json()
    rows = [{"sleeper_id": pid, **stats} for pid, stats in raw.items()]
    df = pd.DataFrame(rows)
    return df


def build_projections(season: int, adp_field: str = "adp_half_ppr") -> pd.DataFrame:
    """Merge players + projections into normalized DataFrame ready for scoring.

    Returns cols: sleeper_id, name, position, team, adp, pts_sleeper_half,
                  gp, and canonical stat cols (pass_yd, rush_yd, rec, etc.)
    """
    players = get_all_players()
    proj = get_season_projections(season)

    merged = players.merge(proj, on="sleeper_id", how="left")

    # ADP
    if adp_field in merged.columns:
        merged["adp"] = pd.to_numeric(merged[adp_field], errors="coerce")
        # Sleeper uses 999.0 as sentinel for "no ADP"
        merged.loc[merged["adp"] >= 999, "adp"] = pd.NA
    else:
        merged["adp"] = pd.NA

    # Canonical stat cols
    for src, dst in STAT_MAP.items():
        if src in merged.columns:
            merged[dst] = pd.to_numeric(merged[src], errors="coerce").fillna(0)
        else:
            merged[dst] = 0

    # Sleeper's pre-scored points (fallback for K/DEF)
    for c in ("pts_half_ppr", "pts_ppr", "pts_std", "gp"):
        if c in merged.columns:
            merged[c] = pd.to_numeric(merged[c], errors="coerce").fillna(0)

    return merged
