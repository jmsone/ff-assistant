"""Run detection and reach detection on the live draft board."""
from __future__ import annotations

from src.live.draft_state import DraftState

RUN_WINDOW = 5   # last N picks
RUN_THRESHOLD = 3  # >= this many of one position = run
REACH_DELTA = 10  # pick_num vs ADP delta threshold


def positional_run(state: DraftState, window: int = RUN_WINDOW,
                   threshold: int = RUN_THRESHOLD) -> dict[str, int]:
    """Positions w/ run in last `window` picks. {pos: count}."""
    recent = state.picks[-window:]
    counts: dict[str, int] = {}
    for p in recent:
        counts[p.position] = counts.get(p.position, 0) + 1
    return {pos: c for pos, c in counts.items() if c >= threshold}


def recent_reach(state: DraftState, adp_lookup: dict[str, float],
                 delta: float = REACH_DELTA) -> list[dict]:
    """Picks in last window that went well ahead of ADP.
    adp_lookup: player_key -> adp.
    Returns list of {name, position, pick_num, adp, delta}.
    """
    reaches = []
    for p in state.picks[-RUN_WINDOW:]:
        adp = adp_lookup.get(p.player_key)
        if adp is None:
            continue
        d = adp - p.pick_num  # positive = reach (pick earlier than adp)
        if d >= delta:
            reaches.append({
                "name": p.player_name,
                "position": p.position,
                "pick_num": p.pick_num,
                "adp": adp,
                "delta": d,
            })
    return reaches
