# FF Assistant

Fantasy football tooling for Yahoo leagues: draft prep, live draft assistant, waiver wire scanner, trade evaluator.

## Setup

```bash
python -m venv .venv
source .venv/Scripts/activate  # Windows Git Bash
pip install yfpy python-dotenv
```

Create `.env` (see `.env.example`) with Yahoo Developer app credentials + your league ID.

## First run — OAuth

```bash
python scripts/auth_setup.py
```

Follow browser prompt, paste verifier code. Refresh token saved to `.env`; no re-auth needed.

## Verify

```bash
python scripts/test_connection.py
```

Prints your league name, teams, roster positions.

## Structure

- `src/` — library code (Yahoo client, scoring, projections, VBD)
- `scripts/` — runnable entry points (auth, draft, waiver scan, trade eval)
- `data/` — cached API responses, projection CSVs
- `auth/` — OAuth token storage (gitignored)
