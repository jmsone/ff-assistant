"""Streamlit draft dashboard. Load cheatsheet, filter, mark drafted, highlight biases.

Run: streamlit run scripts/dashboard.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

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
    s = re.sub(r"[^a-z0-9\s]", "", s)
    s = re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", s)
    return re.sub(r"\s+", " ", s).strip()


def _blend_ensemble(base: pd.DataFrame, espn_df: pd.DataFrame, sleeper_weight: float = 0.5) -> pd.DataFrame:
    base = base.copy()
    base["_key"] = base["name"].apply(_norm_name) + "|" + base["position"]
    espn = espn_df.copy()
    espn["_key"] = espn["name"].apply(_norm_name) + "|" + espn["position"]
    espn_slim = espn[["_key", "fp_espn"]].drop_duplicates(subset="_key")
    merged = base.merge(espn_slim, on="_key", how="left").rename(columns={"fp": "fp_sleeper"})
    espn_wt = 1.0 - sleeper_weight
    ensemble = merged["fp_sleeper"] * sleeper_weight + merged["fp_espn"] * espn_wt
    merged["fp"] = ensemble.where(merged["fp_espn"].notna(), merged["fp_sleeper"])
    merged["fp_delta"] = merged["fp_espn"] - merged["fp_sleeper"]
    return merged.drop(columns=["_key"])

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "output" / "cheatsheet.csv"

# Bias groups
BIAS_TEAMS = {"PHI"}                 # user's Eagles soft spot
BIAS_COLLEGES = {"Penn State"}       # user's alma-mater soft spot

st.set_page_config(page_title="FF Draft Dashboard", layout="wide")


@st.cache_data(ttl=3600, show_spinner="Building projections from Sleeper...")
def rebuild() -> pd.DataFrame:
    cfg = load_config()
    proj = build_projections(cfg.season, adp_field="adp_half_ppr")
    signal = proj["adp"].notna() | (proj.get("pts_half_ppr", 0) > 20)
    proj = proj[signal].reset_index(drop=True)

    offense_mask = proj["position"].isin(["QB", "RB", "WR", "TE"])
    offense = proj[offense_mask].copy()
    offense = score_dataframe(offense, cfg, col="fp")

    kdef = proj[~offense_mask].copy()
    kdef["fp"] = kdef.get("pts_half_ppr", 0)

    all_players = pd.concat([offense, kdef], ignore_index=True)
    espn = get_espn_projections(cfg.season)
    all_players = _blend_ensemble(all_players, espn, sleeper_weight=0.5)
    scored = compute_vbd(all_players, cfg)
    scored = assign_tiers(scored)
    scored["overall_rank"] = scored["vbd"].rank(ascending=False, method="min").astype(int)
    scored["adp_value"] = scored["adp"] - scored["overall_rank"]
    byes = get_bye_weeks(cfg.season)
    scored["bye"] = scored["team"].map(byes).astype("Int64")
    sos = playoff_sos_grades(target_season=cfg.season, prior_season=cfg.season - 1)
    scored = scored.merge(sos[["team", "position", "sos_ratio", "sos_grade", "sos_opps"]],
                          on=["team", "position"], how="left")
    return scored.sort_values("overall_rank").reset_index(drop=True)


def add_bias_col(df: pd.DataFrame) -> pd.DataFrame:
    def tag(row):
        tags = []
        if row.get("team") in BIAS_TEAMS:
            tags.append("EAGLES")
        college = str(row.get("college") or "")
        if any(c.lower() in college.lower() for c in BIAS_COLLEGES):
            tags.append("PSU")
        return " · ".join(tags)

    df = df.copy()
    df["bias"] = df.apply(tag, axis=1)
    return df


def style_biases(row):
    """Row-level styling: Eagles green tint, PSU navy tint, both = both."""
    bias = row.get("bias", "")
    if "EAGLES" in bias and "PSU" in bias:
        return ["background-color: #1a4d3a; color: white"] * len(row)
    if "EAGLES" in bias:
        return ["background-color: #14493a"] * len(row)
    if "PSU" in bias:
        return ["background-color: #1e2a5e"] * len(row)
    return [""] * len(row)


# ---- Session state ----
if "drafted" not in st.session_state:
    st.session_state.drafted = set()
if "my_picks" not in st.session_state:
    st.session_state.my_picks = []

# ---- Sidebar ----
st.sidebar.title("FF Draft Assistant")
cfg = load_config()
st.sidebar.caption(f"League: **{cfg.name}** · {cfg.num_teams} teams · season {cfg.season}")

if st.sidebar.button("Rebuild projections (Sleeper pull)"):
    st.cache_data.clear()
    st.rerun()

positions = st.sidebar.multiselect(
    "Position", ["QB", "RB", "WR", "TE", "K", "DEF"], default=["QB", "RB", "WR", "TE"]
)
max_tier = st.sidebar.slider("Max tier", 1, 15, 8)
hide_drafted = st.sidebar.checkbox("Hide drafted", value=True)
search = st.sidebar.text_input("Search name")
show_bias_only = st.sidebar.checkbox("Show only bias players (Eagles/PSU)", value=False)

st.sidebar.divider()
st.sidebar.subheader("Drafted count")
st.sidebar.metric("Total marked drafted", len(st.session_state.drafted))
st.sidebar.metric("My picks", len(st.session_state.my_picks))

if st.sidebar.button("Reset draft state"):
    st.session_state.drafted = set()
    st.session_state.my_picks = []
    st.rerun()

# ---- Load data ----
df = rebuild()
df = add_bias_col(df)

# ---- Filters ----
view = df[df["position"].isin(positions)]
view = view[view["tier"] <= max_tier]
if hide_drafted:
    view = view[~view["name"].isin(st.session_state.drafted)]
if search:
    view = view[view["name"].str.contains(search, case=False, na=False)]
if show_bias_only:
    view = view[view["bias"] != ""]

# ---- Main pane ----
tab_all, tab_picks = st.tabs(["Best Available", "My Picks"])

with tab_all:
    st.subheader(f"Best available — {len(view)} players (top 60 shown)")
    st.caption("Check **Me** or **Other** on any row to mark drafted. Table refreshes automatically.")

    top = view.head(60).copy().reset_index(drop=True)

    # Editable table with two checkbox cols
    edit_df = top[["overall_rank", "name", "position", "team", "bye", "tier", "pos_rank",
                   "fp", "fp_delta", "vbd", "adp", "adp_value", "sos_grade", "sos_opps",
                   "bias", "injury_status", "college"]].copy()
    edit_df.insert(0, "Me", False)
    edit_df.insert(1, "Other", False)

    edited = st.data_editor(
        edit_df,
        use_container_width=True,
        hide_index=True,
        height=650,
        disabled=[c for c in edit_df.columns if c not in ("Me", "Other")],
        column_config={
            "Me": st.column_config.CheckboxColumn("Me", width="small",
                                                   help="Check when YOU draft this player"),
            "Other": st.column_config.CheckboxColumn("Other", width="small",
                                                     help="Check when someone else drafts"),
            "fp": st.column_config.NumberColumn("FP", format="%.1f",
                                                 help="Ensemble = 0.5 * Sleeper + 0.5 * ESPN"),
            "fp_delta": st.column_config.NumberColumn("Δ", format="%+.0f", width="small",
                                                       help="ESPN minus Sleeper. + = ESPN higher (Sleeper may under-project)."),
            "vbd": st.column_config.NumberColumn("VBD", format="%.1f"),
            "adp": st.column_config.NumberColumn("ADP", format="%.1f"),
            "adp_value": st.column_config.NumberColumn("+/-", format="%+.1f",
                                                       help="ADP minus overall rank; + = value"),
            "overall_rank": st.column_config.NumberColumn("#", width="small"),
            "pos_rank": st.column_config.NumberColumn("PosRk", width="small"),
            "bye": st.column_config.NumberColumn("Bye", width="small",
                                                  help="Bye week. Tiebreaker only — never override VBD."),
            "sos_grade": st.column_config.TextColumn("SoS", width="small",
                                                     help="Playoff wk16-17 matchup grade based on 2025 DvP. A=softest, F=toughest. Tiebreaker only."),
            "sos_opps": st.column_config.TextColumn("Playoff opps", width="medium",
                                                    help="Wk16 > Wk17 opponents"),
        },
        key=f"draft_editor_{len(st.session_state.drafted)}",
    )

    # Process checkbox deltas
    newly_drafted = edited[edited["Me"] | edited["Other"]]
    if len(newly_drafted) > 0:
        for _, row in newly_drafted.iterrows():
            name = row["name"]
            if name in st.session_state.drafted:
                continue
            st.session_state.drafted.add(name)
            if row["Me"]:
                st.session_state.my_picks.append(name)
        st.rerun()

with tab_picks:
    st.subheader(f"My picks ({len(st.session_state.my_picks)})")
    if st.session_state.my_picks:
        my = df[df["name"].isin(st.session_state.my_picks)].copy()
        my["draft_order"] = my["name"].apply(lambda n: st.session_state.my_picks.index(n) + 1)
        my = my.sort_values("draft_order")

        # Positional summary
        counts = my["position"].value_counts().to_dict()
        cols = st.columns(6)
        for i, pos in enumerate(["QB", "RB", "WR", "TE", "K", "DEF"]):
            cols[i].metric(pos, counts.get(pos, 0))

        st.dataframe(
            my[["draft_order", "name", "position", "team", "bye", "sos_grade",
                "tier", "fp", "vbd", "bias", "college"]],
            hide_index=True,
            use_container_width=True,
        )

        # Roster health hints
        st.divider()
        st.subheader("Roster gaps vs league starters")
        for pos, needed in cfg.starters_by_pos.items():
            have = counts.get(pos, 0)
            if have < needed:
                st.warning(f"{pos}: {have}/{needed} starters filled")
            else:
                st.success(f"{pos}: {have}/{needed} OK")

        # Bye-week conflicts (low-pressure hint only — never override VBD)
        st.divider()
        st.subheader("Bye-week overlap")
        bye_view = my[my["bye"].notna()].copy()
        if bye_view.empty:
            st.caption("No bye data yet.")
        else:
            grouped = bye_view.groupby(["bye", "position"]).size().unstack(fill_value=0)
            # Thresholds: single-slot positions warn at 2+, flex-heavy warn at 3+
            single_slot = {"QB", "TE", "K", "DEF"}
            flags = []
            for wk, row in grouped.iterrows():
                for pos, n in row.items():
                    if n == 0:
                        continue
                    threshold = 2 if pos in single_slot else 3
                    if n >= threshold:
                        names = ", ".join(bye_view[(bye_view["bye"] == wk) & (bye_view["position"] == pos)]["name"])
                        flags.append(f"Wk {wk} · {pos} ×{n}: {names}")
            if flags:
                for f in flags:
                    st.warning(f)
                st.caption("Hint: fixable via waivers week-of. Do not reach at draft to avoid.")
            else:
                st.success("No painful bye overlaps.")
            with st.expander("Full bye-by-position table"):
                st.dataframe(grouped, use_container_width=True)
    else:
        st.info("No picks yet. Mark players as drafted in 'Best Available' with 'Who drafted? = ME'.")
