"""Draft state: snake order, picks made, roster tracking.

Pick numbering is 1-indexed. Slot numbering is 1-indexed (1..num_teams).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def snake_slot(pick_num: int, num_teams: int) -> int:
    """Which slot (1..num_teams) is on the clock at pick_num (1-indexed)."""
    if pick_num < 1:
        raise ValueError("pick_num must be >= 1")
    rnd = (pick_num - 1) // num_teams  # 0-indexed round
    idx = (pick_num - 1) % num_teams
    if rnd % 2 == 0:
        return idx + 1
    return num_teams - idx


def user_pick_numbers(user_slot: int, num_teams: int, total_rounds: int) -> list[int]:
    """All pick numbers belonging to user across the draft."""
    picks = []
    for rnd in range(total_rounds):
        if rnd % 2 == 0:
            pick = rnd * num_teams + user_slot
        else:
            pick = rnd * num_teams + (num_teams - user_slot + 1)
        picks.append(pick)
    return picks


@dataclass
class Pick:
    pick_num: int
    slot: int
    player_key: str  # canonical key (e.g. name|pos)
    player_name: str
    position: str
    team: str | None = None


@dataclass
class DraftState:
    num_teams: int
    user_slot: int
    total_rounds: int = 16
    picks: list[Pick] = field(default_factory=list)

    @property
    def current_pick_num(self) -> int:
        return len(self.picks) + 1

    @property
    def current_slot(self) -> int:
        return snake_slot(self.current_pick_num, self.num_teams)

    @property
    def on_the_clock_user(self) -> bool:
        return self.current_slot == self.user_slot

    @property
    def user_pick_nums(self) -> list[int]:
        return user_pick_numbers(self.user_slot, self.num_teams, self.total_rounds)

    def my_next_pick_num(self) -> int | None:
        """Next pick number belonging to user (including current if on clock)."""
        cur = self.current_pick_num
        for p in self.user_pick_nums:
            if p >= cur:
                return p
        return None

    def picks_until_my_next(self) -> int | None:
        """Picks between now and user's next pick, exclusive of current pick.
        0 if user is on the clock right now.
        """
        nxt = self.my_next_pick_num()
        if nxt is None:
            return None
        return nxt - self.current_pick_num

    def my_pick_after_next(self) -> int | None:
        """Pick number user has AFTER their next one — used for survival at next-next turn."""
        cur = self.current_pick_num
        seen_next = False
        for p in self.user_pick_nums:
            if p >= cur:
                if not seen_next:
                    seen_next = True
                    continue
                return p
        return None

    def mark_pick(self, player_key: str, player_name: str, position: str, team: str | None = None) -> Pick:
        pick = Pick(
            pick_num=self.current_pick_num,
            slot=self.current_slot,
            player_key=player_key,
            player_name=player_name,
            position=position,
            team=team,
        )
        self.picks.append(pick)
        return pick

    def undo(self) -> Pick | None:
        if not self.picks:
            return None
        return self.picks.pop()

    def drafted_keys(self) -> set[str]:
        return {p.player_key for p in self.picks}

    def my_roster(self) -> list[Pick]:
        return [p for p in self.picks if p.slot == self.user_slot]

    def roster_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for p in self.my_roster():
            counts[p.position] = counts.get(p.position, 0) + 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        return {
            "num_teams": self.num_teams,
            "user_slot": self.user_slot,
            "total_rounds": self.total_rounds,
            "picks": [p.__dict__ for p in self.picks],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "DraftState":
        picks = [Pick(**p) for p in d.get("picks", [])]
        return cls(
            num_teams=d["num_teams"],
            user_slot=d["user_slot"],
            total_rounds=d.get("total_rounds", 16),
            picks=picks,
        )
