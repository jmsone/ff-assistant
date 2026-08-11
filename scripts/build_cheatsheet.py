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
from src.data.sleeper import build_projections
from src.scoring import score_dataframe

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

    print("\nComputing VBD + tiers...")
    scored = compute_vbd(all_players, cfg)
    scored = assign_tiers(scored)

    # Compute overall rank + value vs ADP
    scored["overall_rank"] = scored["vbd"].rank(ascending=False, method="min").astype(int)
    scored["adp_value"] = scored["adp"] - scored["overall_rank"]

    cols = ["overall_rank", "name", "position", "team", "tier", "pos_rank",
            "fp", "vbd", "adp", "adp_value", "age", "years_exp", "college",
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
