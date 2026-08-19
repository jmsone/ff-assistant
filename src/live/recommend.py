"""Recommendation engine — top-N picks w/ survival-aware VBD math.

Core insight: don't ask "who has the most VBD right now?" Ask
"who has the most VBD that WON'T survive to my next pick?"

Score for candidate C at pick P_now, next pick P_next:
    delta(C) = VBD(C) - max_over_alt(P(alt survives P_next) * VBD(alt))
"Alt" pool = all candidates except C. Higher delta = more urgent to take now.

Roster-need multiplier: penalize positions user has locked; boost positions
still needed. Bias multiplier: tiebreak-within-tier bump for user's fav teams/colleges.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.config import LeagueConfig
from src.live.draft_state import DraftState
from src.live.signals import positional_run
from src.live.survival import add_survival

# Bias config (aligned w/ dashboard.py)
DEFAULT_BIAS_TEAMS: set[str] = {"PHI"}
DEFAULT_BIAS_COLLEGES: set[str] = {"Penn State"}
BIAS_MULT = 1.02  # tiebreak-only, tiny bump

# Fallback if cfg not passed
FALLBACK_TARGET_ROSTER = {"QB": 2, "RB": 5, "WR": 6, "TE": 2, "K": 1, "DEF": 1}

# Bench allocation: how many bench spots to reserve per position.
# Sum should roughly match cfg.roster['BN']. Skewed toward RB/WR (churn positions).
BENCH_ALLOC = {"QB": 1, "RB": 3, "WR": 3, "TE": 1, "K": 0, "DEF": 0}
FLEX_SHARE = {"RB": 0.5, "WR": 0.3, "TE": 0.2}


def target_roster_from_cfg(cfg: LeagueConfig) -> dict[str, int]:
    """Derive per-position roster targets from league config.
    target = ceil(starter_slots + flex_share + bench_alloc).
    """
    starters = cfg.starters_by_pos
    flex = cfg.flex_slots
    out: dict[str, int] = {}
    for pos in ("QB", "RB", "WR", "TE", "K", "DEF"):
        base = starters.get(pos, 0)
        flex_alloc = flex * FLEX_SHARE.get(pos, 0.0)
        bench = BENCH_ALLOC.get(pos, 0)
        target = round(base + flex_alloc + bench)
        out[pos] = max(target, base)
    return out


@dataclass
class Recommendation:
    name: str
    position: str
    team: str
    vbd: float
    adp: float | None
    p_survive_next: float
    delta_score: float
    tier: int | None
    tier_cliff: bool
    tier_drop: float
    roster_need_mult: float
    bias_flag: bool
    run_flag: bool
    reason_short: str
    reason_detail: list[str] = field(default_factory=list)


def _roster_need_mult(pos: str, counts: dict[str, int], targets: dict[str, int]) -> float:
    """Multiplier on VBD. 1.0 = neutral. Punishes stacking one pos past target."""
    have = counts.get(pos, 0)
    target = targets.get(pos, 1)
    if have >= target:
        return 0.5  # already full
    # zero of a required pos = boost hard
    if have == 0 and target >= 2:
        return 1.15
    return 1.0


def _tier_cliff_after_next(df_pos: pd.DataFrame, cur_tier: int,
                            candidate_key: str) -> tuple[bool, float]:
    """Cliff signal + magnitude relative to survival.

    Returns:
      cliff: True if 0 tier-mates expected to survive to user's next pick
      drop_points: VBD difference between this tier's median and next tier's best

    Uses p_survive already computed on df_pos.
    """
    tier_mates = df_pos[(df_pos["tier"] == cur_tier) & (df_pos["player_key"] != candidate_key)]
    survivors = tier_mates["p_survive"].sum() if len(tier_mates) else 0.0
    cliff = survivors < 0.5  # expected # of tier-mates surviving < 0.5

    cur_vbd = df_pos[df_pos["tier"] == cur_tier]["vbd"].max()
    next_tier = df_pos[df_pos["tier"] == cur_tier + 1]
    if len(next_tier):
        drop = float(cur_vbd - next_tier["vbd"].max())
    else:
        drop = 0.0
    return cliff, drop


def _bias_flag(row: pd.Series, teams: set[str], colleges: set[str]) -> bool:
    t = row.get("team")
    c = row.get("college")
    return (isinstance(t, str) and t in teams) or (isinstance(c, str) and c in colleges)


def recommend(
    board: pd.DataFrame,
    state: DraftState,
    cfg: LeagueConfig,
    top_n: int = 5,
    bias_teams: set[str] | None = None,
    bias_colleges: set[str] | None = None,
) -> list[Recommendation]:
    """Top-N recommendations for user's current pick.

    board: cheatsheet DataFrame w/ cols: name, position, team, vbd, tier,
           adp, stddev, optional college.
    state: DraftState (must be user's turn or approximated as such).
    """
    bias_teams = bias_teams if bias_teams is not None else DEFAULT_BIAS_TEAMS
    bias_colleges = bias_colleges if bias_colleges is not None else DEFAULT_BIAS_COLLEGES

    # Strip drafted
    drafted = state.drafted_keys()
    if "player_key" not in board.columns:
        board = board.copy()
        board["player_key"] = board["name"].astype(str) + "|" + board["position"].astype(str)
    avail = board[~board["player_key"].isin(drafted)].copy()
    if avail.empty:
        return []

    # Survival at USER'S next-after-current pick
    next_after = state.my_pick_after_next()
    if next_after is None:
        # Last round or unknown — treat everyone as unlikely to survive
        next_after = state.current_pick_num + state.num_teams * 2
    avail = add_survival(avail, target_pick=next_after)

    # EV of waiting: for each candidate C, max over alt of (p_survive*vbd)
    # Compute per-position because you'd only realistically wait to grab
    # a comparable-need player; but MVP treats all pos equally.
    vbd = pd.to_numeric(avail["vbd"], errors="coerce").fillna(0).to_numpy()
    ps = avail["p_survive"].to_numpy()
    ev = vbd * ps  # expected VBD if you wait for this exact player
    # For each candidate, best alternative EV = max EV excluding self
    if len(ev) > 1:
        # sort desc, pull top 2
        top1_val = ev.max()
        top1_idx = ev.argmax()
        ev_copy = ev.copy()
        ev_copy[top1_idx] = -np.inf
        top2_val = ev_copy.max()
        best_alt = np.full_like(ev, top1_val)
        best_alt[top1_idx] = top2_val
    else:
        best_alt = np.zeros_like(ev)
    delta = vbd - best_alt

    avail["delta_score"] = delta
    avail["p_survive_next"] = ps

    # Roster-need multiplier
    counts = state.roster_counts()
    targets = target_roster_from_cfg(cfg) if cfg is not None else FALLBACK_TARGET_ROSTER
    avail["roster_need_mult"] = avail["position"].map(lambda p: _roster_need_mult(p, counts, targets))
    # Bias flag
    avail["bias_flag"] = avail.apply(lambda r: _bias_flag(r, bias_teams, bias_colleges), axis=1)
    avail["bias_mult"] = avail["bias_flag"].map(lambda b: BIAS_MULT if b else 1.0)

    # Final rank: delta * need * bias
    avail["final_score"] = avail["delta_score"] * avail["roster_need_mult"] * avail["bias_mult"]

    # Run signal from board
    runs = positional_run(state)

    top = avail.sort_values("final_score", ascending=False).head(top_n)

    recs: list[Recommendation] = []
    for _, row in top.iterrows():
        pos = row["position"]
        tier = int(row["tier"]) if pd.notna(row.get("tier")) else None
        cliff = False
        drop = 0.0
        if tier is not None:
            pos_avail = avail[avail["position"] == pos]
            cliff, drop = _tier_cliff_after_next(pos_avail, tier, row["player_key"])

        details = []
        details.append(f"VBD {row['vbd']:.1f} vs replacement")
        if pd.notna(row.get("adp")):
            details.append(f"ADP {row['adp']:.1f} (pick {state.current_pick_num})")
        details.append(f"P(survive to your pick {next_after}) = {row['p_survive_next']:.0%}")
        details.append(f"Δ vs best wait-alternative: {row['delta_score']:.1f}")
        if row["roster_need_mult"] > 1.0:
            details.append(f"Roster need: 0 {pos}s on your roster — boost")
        elif row["roster_need_mult"] < 1.0:
            details.append(f"Roster: already {counts.get(pos,0)} {pos}s — penalized")
        if cliff:
            details.append(f"Tier cliff: no {pos} tier-mates expected to survive; drop to next tier = {drop:.0f} VBD")
        elif drop >= 20:
            details.append(f"Steep tier drop: waiting costs {drop:.0f} VBD if all tier-mates go")
        if pos in runs:
            details.append(f"Positional run: {runs[pos]} {pos}s in last 5 picks")
        if row["bias_flag"]:
            details.append("Bias: Eagles/PSU tiebreak bump applied")

        # Short reason: pick the strongest single signal
        short_parts = []
        if row["p_survive_next"] < 0.15:
            short_parts.append(f"won't survive ({row['p_survive_next']:.0%})")
        if cliff:
            short_parts.append(f"last {pos} in tier")
        if row["roster_need_mult"] > 1.0:
            short_parts.append(f"need {pos}")
        if pos in runs:
            short_parts.append(f"{pos} run")
        if not short_parts:
            short_parts.append(f"top VBD {row['vbd']:.0f}")
        short = f"{pos} • " + ", ".join(short_parts)

        recs.append(Recommendation(
            name=row["name"],
            position=pos,
            team=row.get("team", ""),
            vbd=float(row["vbd"]),
            adp=float(row["adp"]) if pd.notna(row.get("adp")) else None,
            p_survive_next=float(row["p_survive_next"]),
            delta_score=float(row["delta_score"]),
            tier=tier,
            tier_cliff=cliff,
            tier_drop=drop,
            roster_need_mult=float(row["roster_need_mult"]),
            bias_flag=bool(row["bias_flag"]),
            run_flag=pos in runs,
            reason_short=short,
            reason_detail=details,
        ))
    return recs
