"""Fantasy Football Calculator ADP.

Public JSON endpoint, no auth. Includes stddev + high/low for survival math.
Docs: https://fantasyfootballcalculator.com/adp
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

BASE = "https://fantasyfootballcalculator.com/api/v1/adp"

# format keys accepted by FFC
FORMATS = {"standard", "half-ppr", "ppr", "2qb", "dynasty", "rookie"}


def get_adp(fmt: str = "half-ppr", teams: int = 12, year: int | None = None) -> pd.DataFrame:
    """Fetch consensus ADP w/ stddev.

    Returns cols: name, position, team, adp, stddev, high, low, times_drafted, bye.
    Position normalized to QB/RB/WR/TE/K/DEF.
    """
    if fmt not in FORMATS:
        raise ValueError(f"fmt must be one of {FORMATS}")
    params = {"teams": teams, "position": "all"}
    if year is not None:
        params["year"] = year
    url = f"{BASE}/{fmt}"
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    payload = r.json()
    players = payload.get("players", [])
    df = pd.DataFrame(players)
    if df.empty:
        return df

    # normalize columns
    df = df.rename(columns={
        "player_id": "ffc_id",
        "adp": "adp",
        "adp_formatted": "adp_str",
        "times_drafted": "times_drafted",
        "high": "high",
        "low": "low",
        "stdev": "stddev",
        "bye": "bye",
    })

    # DST -> DEF for consistency w/ Sleeper convention
    df["position"] = df["position"].replace({"DST": "DEF", "PDST": "DEF"})

    keep = [c for c in ["name", "position", "team", "adp", "stddev", "high", "low",
                        "times_drafted", "bye", "ffc_id"] if c in df.columns]
    return df[keep].reset_index(drop=True)
