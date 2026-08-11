"""Wipe cached Yahoo OAuth token from .env. Re-run auth_setup.py after."""
import sys
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

KEEP_KEYS = {"YAHOO_CONSUMER_KEY", "YAHOO_CONSUMER_SECRET", "YAHOO_APP_ID",
             "YAHOO_LEAGUE_ID", "YAHOO_GAME_CODE", "YAHOO_SEASON"}

lines = ENV_PATH.read_text().splitlines()
kept = [ln for ln in lines if not ln.strip() or ln.split("=", 1)[0] in KEEP_KEYS]
ENV_PATH.write_text("\n".join(kept) + "\n")
print(f"Wiped token fields. Kept: {sorted(KEEP_KEYS)}")
