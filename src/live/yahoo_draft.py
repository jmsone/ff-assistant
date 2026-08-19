"""Yahoo draft-room polling to auto-populate DraftState.

Untested end-to-end — depends on Yahoo dev approval landing. Once OAuth works,
poll every ~5s during draft, diff picks against local state, mark new ones.

yfpy exposes get_league_draft_results() returning list of draft-result objects
with pick, round, team_key, player_key. Player names come from a separate
get_player() call, so we cache player_key -> (name, pos, team) on first fetch.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from src.live.draft_state import DraftState


@dataclass
class YahooPick:
    pick_num: int
    round: int
    team_key: str
    player_key: str
    player_name: str
    position: str
    nfl_team: str | None


def fetch_draft_results(client: Any) -> list[YahooPick]:
    """Fetch draft results + player metadata from Yahoo.

    client: instance of YahooFantasySportsQuery (see src/yahoo_client.py).
    Returns picks sorted by pick_num ascending.
    """
    draft = client.get_league_draft_results()
    picks: list[YahooPick] = []
    for d in draft:
        player_key = getattr(d, "player_key", None)
        if not player_key:
            continue
        # Player lookup — yfpy: get_player_stats_for_season or get_player_metadata_by_player_key
        try:
            p = client.get_player_metadata_by_player_key(player_key)
            name = getattr(p.name, "full", None) or str(p.name)
            pos = getattr(p, "display_position", None) or getattr(p, "primary_position", "")
            nfl = getattr(p, "editorial_team_abbr", None)
        except Exception:
            name, pos, nfl = player_key, "", None
        picks.append(YahooPick(
            pick_num=int(getattr(d, "pick", 0)),
            round=int(getattr(d, "round", 0)),
            team_key=str(getattr(d, "team_key", "")),
            player_key=player_key,
            player_name=name,
            position=pos.upper() if pos else "",
            nfl_team=nfl,
        ))
    picks.sort(key=lambda x: x.pick_num)
    return picks


def sync_to_state(state: DraftState, yahoo_picks: list[YahooPick],
                  key_fn: Callable[[str, str], str] | None = None) -> int:
    """Apply new picks from Yahoo to local DraftState. Returns count added.

    key_fn(name, position) -> canonical player_key used by the board.
    If None, uses "name|position".
    """
    if key_fn is None:
        key_fn = lambda n, p: f"{n}|{p}"
    added = 0
    have = len(state.picks)
    for yp in yahoo_picks:
        if yp.pick_num <= have:
            continue  # already recorded
        state.mark_pick(
            player_key=key_fn(yp.player_name, yp.position),
            player_name=yp.player_name,
            position=yp.position,
            team=yp.nfl_team,
        )
        added += 1
    return added
