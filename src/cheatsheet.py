"""VBD (Value Based Drafting) + tier construction.

Replacement level = fantasy points of the Nth-ranked player at position,
where N = number of league-wide starters at that position (incl FLEX share).
VBD = player_fp - replacement_fp. Tiers = gaps > threshold between adjacent VBDs.
"""
from __future__ import annotations

import pandas as pd

from src.config import LeagueConfig


def compute_vbd(df: pd.DataFrame, cfg: LeagueConfig, fp_col: str = "fp") -> pd.DataFrame:
    """Add 'replacement', 'vbd', 'pos_rank' columns."""
    out = df.copy()
    out[fp_col] = pd.to_numeric(out[fp_col], errors="coerce").fillna(0)
    out["pos_rank"] = (
        out.groupby("position")[fp_col]
        .rank(ascending=False, method="min")
        .fillna(9999)
        .astype(int)
    )

    replacement_by_pos: dict[str, float] = {}
    for pos in out["position"].unique():
        n_starters = cfg.league_starters(pos)
        if n_starters <= 0:
            # K/DEF etc: use league size as baseline
            n_starters = cfg.num_teams
        pos_df = out[out["position"] == pos].sort_values(fp_col, ascending=False)
        if len(pos_df) >= n_starters:
            replacement_by_pos[pos] = pos_df.iloc[n_starters - 1][fp_col]
        else:
            replacement_by_pos[pos] = pos_df[fp_col].min()

    out["replacement"] = out["position"].map(replacement_by_pos)
    out["vbd"] = out[fp_col] - out["replacement"]
    return out.sort_values("vbd", ascending=False).reset_index(drop=True)


def assign_tiers(df: pd.DataFrame, gap_thresholds: dict[str, float] | None = None,
                 gap_mult: float = 3.5, max_tier_size: int = 8,
                 tier_window: int = 30) -> pd.DataFrame:
    """Assign tier number per position based on adaptive VBD gaps.

    A tier break fires when a gap exceeds max(floor, gap_mult * median_gap),
    computed over the top `tier_window` players at that position (positions
    beyond the window rarely get drafted so their gaps shouldn't dilute).

    Also caps tier size — forces a break after `max_tier_size` consecutive players
    to prevent runaway single-tier situations when the VBD curve is smooth.

    gap_thresholds: per-position hard floor. Defaults tuned for half-PPR VBD scale.
    """
    floors = gap_thresholds or {
        "QB": 12, "RB": 10, "WR": 8, "TE": 8, "K": 3, "DEF": 3,
    }
    out = df.copy()
    out["tier"] = 0

    for pos in out["position"].dropna().unique():
        floor = floors.get(pos, 5)
        mask = out["position"] == pos
        pos_df = out[mask].sort_values("vbd", ascending=False).copy()
        if pos_df.empty:
            continue
        # Adaptive threshold from top-N gaps
        window_vbd = pos_df["vbd"].head(tier_window)
        gaps = (-window_vbd.diff().dropna())
        median_gap = gaps.median() if len(gaps) else 0.0
        thresh = max(floor, gap_mult * (median_gap or 0.0))

        tiers = []
        current_tier = 1
        tier_count = 0
        prev_vbd: float | None = None
        for _, row in pos_df.iterrows():
            gap = (prev_vbd - row["vbd"]) if prev_vbd is not None else 0.0
            if prev_vbd is not None and (gap > thresh or tier_count >= max_tier_size):
                current_tier += 1
                tier_count = 0
            tiers.append(current_tier)
            tier_count += 1
            prev_vbd = row["vbd"]
        out.loc[pos_df.index, "tier"] = tiers
    return out


def add_adp_value(df: pd.DataFrame, adp_df: pd.DataFrame) -> pd.DataFrame:
    """Merge ADP by player name, compute overall_rank vs ADP delta.
    Positive delta = player is being drafted later than value warrants (steal).
    """
    out = df.copy()
    out["overall_rank"] = out["vbd"].rank(ascending=False, method="min").astype(int)

    adp = adp_df.copy()
    adp.columns = [c.lower() for c in adp.columns]
    name_col = next((c for c in ("player", "player_name", "name") if c in adp.columns), None)
    adp_col = next((c for c in ("avg", "adp", "avg_pick") if c in adp.columns), None)
    if name_col is None or adp_col is None:
        print("WARN: ADP frame missing name or avg columns; skipping merge")
        out["adp"] = pd.NA
        out["adp_value"] = pd.NA
        return out

    adp_clean = adp[[name_col, adp_col]].rename(columns={name_col: "name", adp_col: "adp"})
    adp_clean["name"] = adp_clean["name"].astype(str).str.strip()
    out = out.merge(adp_clean, on="name", how="left")
    out["adp"] = pd.to_numeric(out["adp"], errors="coerce")
    out["adp_value"] = out["adp"] - out["overall_rank"]  # positive = value
    return out
