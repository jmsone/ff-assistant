"""Verify Yahoo API access. Prints league, teams, current roster."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.yahoo_client import get_client


def main() -> None:
    client = get_client()

    league = client.get_league_info()
    print(f"League: {league.name}")
    print(f"  Season: {league.season}")
    print(f"  Teams:  {league.num_teams}")
    print(f"  Scoring: {league.scoring_type}")
    print(f"  Current week: {league.current_week}\n")

    teams = client.get_league_teams()
    print(f"Teams in league:")
    for t in teams:
        print(f"  {t.team_id:>3}  {t.name}  (manager: {t.managers[0].manager.nickname if t.managers else '?'})")

    settings = client.get_league_settings()
    print(f"\nRoster positions:")
    for pos in settings.roster_positions:
        print(f"  {pos.roster_position.position} x{pos.roster_position.count}")


if __name__ == "__main__":
    main()
