"""Live draft assistant — Streamlit UI.

Run: streamlit run scripts/live_draft.py

Manual pick entry. Top-5 recs w/ survival-aware scoring. Undo. Roster panel.
Run/reach banners.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from src.config import load_config
from src.data.ffc import get_adp as get_ffc_adp
from src.data.normalize import canonical_name
from src.live.draft_state import DraftState
from src.live.recommend import recommend
from src.live.signals import positional_run, recent_reach

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "output" / "cheatsheet.csv"

st.set_page_config(page_title="Live Draft Assistant", layout="wide")


@st.cache_data(ttl=3600, show_spinner="Loading board…")
def load_board() -> pd.DataFrame:
    if not CSV_PATH.exists():
        st.error(f"No cheatsheet at {CSV_PATH}. Run `python scripts/build_cheatsheet.py` first.")
        st.stop()
    board = pd.read_csv(CSV_PATH)
    ffc = get_ffc_adp("half-ppr", 12)
    ffc["_key"] = ffc["name"].apply(canonical_name) + "|" + ffc["position"]
    board["_key"] = board["name"].apply(canonical_name) + "|" + board["position"]
    ffc_slim = ffc[["_key", "stddev", "adp"]].rename(columns={"adp": "adp_ffc"}).drop_duplicates("_key")
    board = board.merge(ffc_slim, on="_key", how="left").drop(columns=["_key"])
    board["adp"] = board["adp"].fillna(board["adp_ffc"])
    board["player_key"] = board["name"].astype(str) + "|" + board["position"].astype(str)
    return board


def init_state():
    if "draft_state" not in st.session_state:
        st.session_state.draft_state = None
    if "num_teams" not in st.session_state:
        st.session_state.num_teams = 12
    if "user_slot" not in st.session_state:
        st.session_state.user_slot = 5
    if "total_rounds" not in st.session_state:
        st.session_state.total_rounds = 16
    if "bias_teams" not in st.session_state:
        st.session_state.bias_teams = "PHI"
    if "bias_colleges" not in st.session_state:
        st.session_state.bias_colleges = "Penn State"
    if "yahoo_sync" not in st.session_state:
        st.session_state.yahoo_sync = False


def setup_screen():
    st.title("Live Draft Assistant — Setup")
    st.write("Enter league details, then start draft.")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.session_state.num_teams = st.number_input(
            "Number of teams", min_value=4, max_value=16, value=st.session_state.num_teams, step=1
        )
    with col2:
        st.session_state.user_slot = st.number_input(
            "Your draft slot (1..N)", min_value=1,
            max_value=int(st.session_state.num_teams),
            value=min(st.session_state.user_slot, int(st.session_state.num_teams)), step=1
        )
    with col3:
        st.session_state.total_rounds = st.number_input(
            "Total rounds", min_value=8, max_value=25, value=st.session_state.total_rounds, step=1
        )
    st.session_state.bias_teams = st.text_input("Bias teams (comma-sep, e.g. PHI)", st.session_state.bias_teams)
    st.session_state.bias_colleges = st.text_input("Bias colleges (comma-sep)", st.session_state.bias_colleges)
    st.session_state.yahoo_sync = st.checkbox(
        "Auto-sync from Yahoo draft room (requires OAuth approval)",
        value=st.session_state.yahoo_sync,
        help="Polls Yahoo every 5s and mirrors picks locally. Falls back to manual on error.",
    )
    if st.button("Start Draft", type="primary"):
        st.session_state.draft_state = DraftState(
            num_teams=int(st.session_state.num_teams),
            user_slot=int(st.session_state.user_slot),
            total_rounds=int(st.session_state.total_rounds),
        )
        st.rerun()


def render_recs(recs):
    if not recs:
        st.info("No recommendations — board empty or draft over.")
        return
    for i, r in enumerate(recs, start=1):
        highlight = "🟢" if i == 1 else "  "
        st.markdown(f"**{highlight} #{i} {r.name}** ({r.position}, {r.team}) — {r.reason_short}")
        with st.expander("Detail"):
            for d in r.reason_detail:
                st.write(f"- {d}")


def render_roster(state: DraftState):
    st.subheader("Your roster")
    picks = state.my_roster()
    if not picks:
        st.write("_(empty)_")
        return
    df = pd.DataFrame([{
        "Rd": (p.pick_num - 1) // state.num_teams + 1,
        "Pick": p.pick_num,
        "Pos": p.position,
        "Player": p.player_name,
        "Team": p.team or "",
    } for p in picks])
    st.dataframe(df, use_container_width=True, hide_index=True)
    counts = state.roster_counts()
    st.write(" · ".join(f"{k}: {v}" for k, v in sorted(counts.items())))


def render_signals(state: DraftState, board: pd.DataFrame):
    runs = positional_run(state)
    if runs:
        parts = [f"{c} {p}s in last 5" for p, c in runs.items()]
        st.warning(f"🏃 Positional run detected: {', '.join(parts)}")
    adp_lookup = dict(zip(board["player_key"], board["adp"]))
    reaches = recent_reach(state, adp_lookup)
    if reaches:
        parts = [f"{r['name']} (pick {r['pick_num']}, ADP {r['adp']:.0f}, Δ+{r['delta']:.0f})" for r in reaches]
        st.info(f"📈 Recent reach: {'; '.join(parts)}")


def draft_screen(board: pd.DataFrame, cfg):
    state: DraftState = st.session_state.draft_state
    total_picks = state.num_teams * state.total_rounds

    # Top bar
    left, mid, right = st.columns([2, 2, 1])
    with left:
        st.metric("Current pick", f"{state.current_pick_num} / {total_picks}")
    with mid:
        rnd = (state.current_pick_num - 1) // state.num_teams + 1
        oc = "🟢 YOU" if state.on_the_clock_user else f"Slot {state.current_slot}"
        st.metric(f"Round {rnd}", f"On clock: {oc}")
    with right:
        if st.button("↶ Undo", disabled=len(state.picks) == 0):
            state.undo()
            st.rerun()

    if st.session_state.get("yahoo_sync"):
        try:
            from src.live.yahoo_draft import fetch_draft_results, sync_to_state
            from src.yahoo_client import get_client
            client = get_client()
            picks = fetch_draft_results(client)
            added = sync_to_state(state, picks)
            if added:
                st.toast(f"Synced {added} pick(s) from Yahoo")
        except Exception as e:
            st.warning(f"Yahoo sync failed: {e}. Continuing manually.")

    render_signals(state, board)

    # Layout: recs | pick entry | roster
    col_recs, col_entry, col_roster = st.columns([3, 3, 2])

    with col_recs:
        st.subheader("🎯 Top recommendations")
        bt = {t.strip().upper() for t in st.session_state.bias_teams.split(",") if t.strip()}
        bc = {c.strip() for c in st.session_state.bias_colleges.split(",") if c.strip()}
        recs = recommend(board, state, cfg, top_n=5, bias_teams=bt, bias_colleges=bc)
        render_recs(recs)

    with col_entry:
        st.subheader("Record pick")
        drafted = state.drafted_keys()
        avail = board[~board["player_key"].isin(drafted)].copy()
        pos_filter = st.multiselect("Position filter", ["QB", "RB", "WR", "TE", "K", "DEF"], default=[])
        if pos_filter:
            avail = avail[avail["position"].isin(pos_filter)]
        search = st.text_input("Search")
        if search:
            avail = avail[avail["name"].str.contains(search, case=False, na=False)]
        show = avail.sort_values("overall_rank").head(50)[["overall_rank", "name", "position", "team", "tier", "vbd", "adp"]]

        hdr = st.columns([1, 3, 1, 1, 1, 1, 1, 1])
        for c, label in zip(hdr, ["#", "Name", "Pos", "Team", "Tier", "VBD", "ADP", ""]):
            c.markdown(f"**{label}**")

        for _, row in show.iterrows():
            cols = st.columns([1, 3, 1, 1, 1, 1, 1, 1])
            cols[0].write(f"#{int(row['overall_rank'])}")
            cols[1].write(f"**{row['name']}**")
            cols[2].write(row["position"])
            cols[3].write(row["team"])
            cols[4].write(f"T{int(row['tier'])}" if pd.notna(row["tier"]) else "-")
            cols[5].write(f"{row['vbd']:.0f}")
            cols[6].write(f"{row['adp']:.1f}" if pd.notna(row["adp"]) else "-")
            if cols[7].button("Draft", key=f"draft_{row['name']}_{row['position']}"):
                state.mark_pick(
                    player_key=f"{row['name']}|{row['position']}",
                    player_name=row["name"],
                    position=row["position"],
                    team=row["team"],
                )
                st.rerun()

    with col_roster:
        render_roster(state)
        st.divider()
        if st.button("🔄 Reset draft"):
            st.session_state.draft_state = None
            st.rerun()


def main():
    init_state()
    if st.session_state.draft_state is None:
        setup_screen()
        return
    cfg = load_config()
    board = load_board()
    draft_screen(board, cfg)


if __name__ == "__main__":
    main()
