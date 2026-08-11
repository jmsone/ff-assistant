"""League config loader."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "league.yaml"


@dataclass
class LeagueConfig:
    name: str
    season: int
    num_teams: int
    roster: dict[str, int]
    scoring: dict[str, float]
    playoff_weeks: list[int] = field(default_factory=lambda: [16, 17])
    playoff_weight_multiplier: float = 2.0

    @property
    def starters_by_pos(self) -> dict[str, int]:
        """Starting slots per position (excluding FLEX/BN/IR)."""
        return {k: v for k, v in self.roster.items() if k not in ("FLEX", "BN", "IR")}

    @property
    def flex_slots(self) -> int:
        return self.roster.get("FLEX", 0)

    def league_starters(self, pos: str) -> int:
        """Approx league-wide starter count at position, incl FLEX share.
        FLEX gets split 50/30/20 across RB/WR/TE per typical usage.
        """
        base = self.starters_by_pos.get(pos, 0) * self.num_teams
        flex_share = {"RB": 0.5, "WR": 0.3, "TE": 0.2}.get(pos, 0.0)
        flex = self.flex_slots * self.num_teams * flex_share
        return int(round(base + flex))


def load_config(path: Path | str = DEFAULT_CONFIG) -> LeagueConfig:
    data: dict[str, Any] = yaml.safe_load(Path(path).read_text())
    return LeagueConfig(**data)
