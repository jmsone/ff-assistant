# FF — Fantasy Football Draft & Analysis Toolkit

Python toolkit for redraft fantasy football leagues: projection ensembling, custom-scoring conversion, VBD-based rankings, tiering, playoff strength-of-schedule, and a live draft dashboard.

Built for a half-PPR Yahoo league but the scoring engine reads your league's exact rules from YAML, so it works with any ruleset.

## What it does

**Phase 1 — Draft prep (built)**
- Pulls player projections from Sleeper + ESPN, blends them into an ensemble
- Converts raw stat projections into fantasy points using *your* league's scoring rules (`config/league.yaml`)
- Computes Value-Based Drafting (VBD) scores against positional replacement level
- Assigns tiers via 1D k-means on VBD gaps
- Adds bye weeks and playoff-week strength-of-schedule grades
- Exports a CSV cheatsheet and a printable PDF

**Phase 2 — Live draft assistant (in progress)**
- Streamlit dashboard: filter by position, mark players drafted with one click, watch tiers collapse in real time
- Bias-aware highlighting (e.g., flag alumni / hometeam players — tiebreaker within a tier only, never overrides VBD)
- Survival-probability estimates: "will this player be there at your next pick?"
- Yahoo live-draft integration scaffolded (blocked on Yahoo API approval — see below)

**Phase 3 — In-season tools (planned)**
- Waiver-wire usage scanner (target share / snap-count deltas)
- Trade evaluator using rest-of-season VBD

## Architecture

```
src/
├── config.py         # YAML loader for league rules
├── scoring.py        # stat-line → fantasy points (any ruleset)
├── cheatsheet.py     # VBD + tier assignment
├── data/
│   ├── sleeper.py    # Sleeper projections (primary source)
│   ├── espn.py       # ESPN projections (ensemble partner)
│   ├── fantasypros.py
│   ├── schedule.py   # NFL schedule + bye weeks (nfl_data_py)
│   ├── sos.py        # playoff-week strength-of-schedule grades
│   └── normalize.py  # name matching across data sources
├── live/             # live-draft state, recommendations, survival model
└── yahoo_client.py   # Yahoo Fantasy API wrapper (yfpy)

scripts/
├── build_cheatsheet.py  # produce ranked CSV
├── build_pdf.py         # produce printable PDF
├── dashboard.py         # Streamlit live-draft app
└── auth_setup.py        # one-time Yahoo OAuth
```

## Setup

```bash
python -m venv .venv
source .venv/Scripts/activate  # Windows Git Bash; use .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env           # then fill in Yahoo creds (optional for Phase 1)
```

Edit `config/league.yaml` to match your league's scoring and roster.

## Usage

**Generate the cheatsheet:**
```bash
python scripts/build_cheatsheet.py
# → output/cheatsheet.csv
```

**Run the live-draft dashboard:**
```bash
streamlit run scripts/dashboard.py
```

**Build a printable PDF:**
```bash
python scripts/build_pdf.py
```

## Yahoo API status

The Yahoo Fantasy Sports API requires per-app manual approval for read access. This project's OAuth flow (`scripts/auth_setup.py`) and Yahoo client wrapper are complete and tested against Yahoo's mock endpoints, but full league sync is gated on Yahoo's approval process.

**Phase 1 (cheatsheet, dashboard, PDF) works standalone** — no Yahoo account required. Sleeper + ESPN projections + `nfl_data_py` are the primary data sources.

## Design notes

- **Scoring is data-driven, not hardcoded.** `src/scoring.py` reads scoring rules from YAML and applies them via vectorized pandas operations to any projection dataframe. Swap leagues by editing one config file.
- **Ensemble > single source.** Sleeper + ESPN blends catch projection outliers; single-source rankings systematically overrate their favorites.
- **VBD, not raw points.** A 300-point RB is worth more than a 300-point QB because the replacement RB is much worse than the replacement QB. Cheatsheet rankings reflect scarcity.
- **Tiers via k-means on VBD gaps**, not fixed tier sizes. Real drafts have natural cliffs; the algorithm finds them.

## License

MIT — see [LICENSE](LICENSE).
