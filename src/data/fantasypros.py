"""FantasyPros scraper for consensus projections + ADP.
Free public pages; parses HTML tables. No API key needed.
"""
from __future__ import annotations

from io import StringIO

import pandas as pd
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
}

POSITIONS = ["qb", "rb", "wr", "te", "k", "dst"]

# FantasyPros projection URLs by position + scoring format.
# scoring = "STD" | "HALF" | "PPR"
PROJ_URL = "https://www.fantasypros.com/nfl/projections/{pos}.php?week=draft&scoring={scoring}"

ADP_URL = "https://www.fantasypros.com/nfl/adp/{fmt}.php"  # fmt: standard, half-point-ppr, ppr


def _get_soup(url: str) -> BeautifulSoup:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.text, "lxml")


def _table_to_df(soup: BeautifulSoup, table_id: str = "data") -> pd.DataFrame:
    table = soup.find("table", id=table_id) or soup.find("table")
    if table is None:
        raise RuntimeError("No table found")
    return pd.read_html(StringIO(str(table)))[0]


def get_projections(position: str, scoring: str = "HALF") -> pd.DataFrame:
    """Preseason (draft-week) projections for one position."""
    if position.lower() not in POSITIONS:
        raise ValueError(f"position must be one of {POSITIONS}")
    url = PROJ_URL.format(pos=position.lower(), scoring=scoring)
    soup = _get_soup(url)
    df = _table_to_df(soup)
    # FantasyPros uses multi-level column headers; flatten
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [
            f"{a}_{b}".strip("_").lower().replace(" ", "_")
            if a and not a.startswith("Unnamed") else b.lower().replace(" ", "_")
            for a, b in df.columns
        ]
    else:
        df.columns = [c.lower().replace(" ", "_") for c in df.columns]
    df["position"] = position.upper()
    return df


def get_adp(fmt: str = "half-point-ppr") -> pd.DataFrame:
    """Consensus ADP across sources."""
    url = ADP_URL.format(fmt=fmt)
    soup = _get_soup(url)
    df = _table_to_df(soup)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [b.lower().replace(" ", "_") for _, b in df.columns]
    else:
        df.columns = [c.lower().replace(" ", "_") for c in df.columns]
    return df


def get_all_projections(scoring: str = "HALF") -> pd.DataFrame:
    """Concat projections across all positions."""
    frames = []
    for pos in POSITIONS:
        try:
            frames.append(get_projections(pos, scoring=scoring))
        except Exception as e:
            print(f"WARN: {pos} projections failed: {e}")
    return pd.concat(frames, ignore_index=True)
