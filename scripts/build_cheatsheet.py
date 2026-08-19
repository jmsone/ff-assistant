"""Build draft cheat sheet: Sleeper projections → user-scoring → VBD → tiers → CSV.

QB/RB/WR/TE use stat-based scoring vs user's exact league rules.
K/DEF fall back to Sleeper's pre-computed pts_half_ppr (close enough for MVP).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from src.cheatsheet import assign_tiers, compute_vbd
from src.config import load_config
from src.data.espn import get_projections as get_espn_projections
from src.data.schedule import get_bye_weeks
from src.data.sleeper import build_projections
from src.data.sos import playoff_sos_grades
from src.scoring import score_dataframe

import re


def _norm_name(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s]", "", s)   # strip punctuation
    s = re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", s)  # strip suffix
    return re.sub(r"\s+", " ", s).strip()


def _ensemble_projections(base: pd.DataFrame, espn_df: pd.DataFrame,
                          sleeper_weight: float = 0.5) -> pd.DataFrame:
    """Merge Sleeper (base) with ESPN projections, produce ensemble fp.

    Match on normalized name + position. If a Sleeper row has no ESPN match,
    keep Sleeper fp unchanged (fp_espn = NaN).
    """
    base = base.copy()
    base["_key"] = base["name"].apply(_norm_name) + "|" + base["position"]
    espn = espn_df.copy()
    espn["_key"] = espn["name"].apply(_norm_name) + "|" + espn["position"]
    espn_slim = espn[["_key", "fp_espn"]].drop_duplicates(subset="_key")

    merged = base.merge(espn_slim, on="_key", how="left")
    merged = merged.rename(columns={"fp": "fp_sleeper"})

    espn_wt = 1.0 - sleeper_weight
    ensemble = merged["fp_sleeper"] * sleeper_weight + merged["fp_espn"] * espn_wt
    merged["fp"] = ensemble.where(merged["fp_espn"].notna(), merged["fp_sleeper"])
    merged["fp_delta"] = merged["fp_espn"] - merged["fp_sleeper"]
    return merged.drop(columns=["_key"])

OUT_DIR = Path(__file__).resolve().parent.parent / "output"
OUT_DIR.mkdir(exist_ok=True)


def main() -> None:
    cfg = load_config()
    print(f"League: {cfg.name}  season={cfg.season}  teams={cfg.num_teams}")

    print("\nPulling Sleeper season projections...")
    proj = build_projections(cfg.season, adp_field="adp_half_ppr")
    print(f"  Total players with data: {(proj['adp'].notna() | (proj.get('pts_half_ppr', 0) > 0)).sum()}")

    # Filter to players with any signal (adp present OR meaningful projected pts)
    signal = proj["adp"].notna() | (proj.get("pts_half_ppr", 0) > 20)
    proj = proj[signal].reset_index(drop=True)

    # QB/RB/WR/TE: our scoring
    offense_mask = proj["position"].isin(["QB", "RB", "WR", "TE"])
    offense = proj[offense_mask].copy()
    offense = score_dataframe(offense, cfg, col="fp")

    # K/DEF: Sleeper default (close enough for MVP)
    kdef = proj[~offense_mask].copy()
    kdef["fp"] = kdef.get("pts_half_ppr", 0)

    all_players = pd.concat([offense, kdef], ignore_index=True)

    print(f"  After scoring: {len(all_players)} players ({(all_players['fp'] > 0).sum()} with points)")

    print("\nPulling ESPN projections (ensemble second source)...")
    espn = get_espn_projections(cfg.season)
    print(f"  ESPN: {len(espn)} players")
    all_players = _ensemble_projections(all_players, espn, sleeper_weight=0.5)
    matched = all_players["fp_espn"].notna().sum()
    print(f"  Ensemble merge: {matched}/{len(all_players)} matched to ESPN")

    print("\nComputing VBD + tiers...")
    scored = compute_vbd(all_players, cfg)
    scored = assign_tiers(scored)

    # Compute overall rank + value vs ADP
    scored["overall_rank"] = scored["vbd"].rank(ascending=False, method="min").astype(int)
    scored["adp_value"] = scored["adp"] - scored["overall_rank"]

    # Bye weeks (nflverse). Tiebreaker column, not baked into VBD.
    byes = get_bye_weeks(cfg.season)
    scored["bye"] = scored["team"].map(byes).astype("Int64")

    # Playoff SoS wk16-17 (prior-season DvP). Tiebreaker only.
    sos = playoff_sos_grades(target_season=cfg.season, prior_season=cfg.season - 1)
    scored = scored.merge(sos[["team", "position", "sos_ratio", "sos_grade", "sos_opps"]],
                          on=["team", "position"], how="left")

    cols = ["overall_rank", "name", "position", "team", "bye", "tier", "pos_rank",
            "fp", "fp_sleeper", "fp_espn", "fp_delta",
            "vbd", "adp", "adp_value", "sos_grade", "sos_ratio", "sos_opps",
            "age", "years_exp", "college",
            "injury_status", "depth_chart_order", "gp"]
    cols = [c for c in cols if c in scored.columns]
    scored = scored[cols].sort_values("overall_rank")

    out_path = OUT_DIR / "cheatsheet.csv"
    scored.to_csv(out_path, index=False, float_format="%.2f")
    print(f"\nWrote {len(scored)} players to {out_path}")

    print("\nTop 30 overall:")
    print(scored.head(30).to_string(index=False))

    print("\nBiggest ADP values (draft later than value suggests, +30):")
    values = scored[scored["adp_value"] > 30].sort_values("vbd", ascending=False).head(15)
    print(values[["overall_rank", "name", "position", "tier", "fp", "adp", "adp_value"]].to_string(index=False))


if __name__ == "__main__":
    main()
