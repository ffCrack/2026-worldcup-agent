---
name: 2026-world-cup-simulator
description: Maintain and operate the local 2026 World Cup simulator project. Use when Codex needs to update match data, rebuild Elo ratings, adjust tournament bracket simulation logic, run Monte Carlo forecasts, debug the Python agents in src/data_loader.py, src/data_agent.py, or src/sim_agent.py, or explain outputs from this repository's CSV/JSON based football prediction pipeline.
---

# 2026 World Cup Simulator

## Overview

Use this skill for the Python project rooted at `worldcup_2026_agent_2`. The project loads historical match rows from CSV, updates Elo-style team ratings, saves ratings to JSON, and runs Monte Carlo knockout simulations.

## Project Map

- `main.py`: End-to-end pipeline entry point.
- `data/world_cup_history.csv`: Match input data with `date`, `home_team`, `away_team`, `home_score`, `away_score`, and `stage`.
- `team_ratings.json`: Current Elo ratings used by simulations.
- `src/data_loader.py`: Creates or loads the CSV and normalizes types.
- `src/data_agent.py`: Applies Elo updates from match results and writes ratings.
- `src/sim_agent.py`: Simulates single matches, brackets, and Monte Carlo tournament outcomes.

## Workflow

1. Inspect `main.py` and the relevant file in `src/` before changing behavior.
2. Preserve the CSV schema unless the user explicitly asks for a data model change.
3. Keep generated rating output deterministic where practical; avoid unrelated churn in `team_ratings.json`.
4. Run the smallest relevant command after edits:

```bash
python3 main.py
```

For focused checks, run an individual module:

```bash
python3 src/data_loader.py
python3 src/data_agent.py
python3 src/sim_agent.py
```

## Common Tasks

### Add Match Results

Append rows to `data/world_cup_history.csv` using the existing schema. Scores must be integer values. Dates should use ISO format, for example `2026-06-27`.

After data changes, rebuild ratings by running `python3 main.py` or by using `DataAndRatingAgent.process_historical_data()` if only the rating rebuild is needed.

### Adjust Elo Behavior

Edit `src/data_agent.py`. Check:

- `k_factor` controls rating volatility.
- `get_rating()` defaults new teams to `1500.0`.
- `update_elo()` maps wins to `1.0`, losses to `0.0`, and draws to `0.5`.

Keep rating rounding consistent unless precision is part of the requested change.

### Adjust Simulation Behavior

Edit `src/sim_agent.py`. Check:

- `simulate_single_match()` handles Elo-derived win probability.
- `allow_draw=True` is for group-stage style behavior.
- `simulate_bracket()` expects an even knockout list and advances winners pairwise.
- `run_monte_carlo()` prints title probabilities from repeated bracket runs.

If adding seeded randomness, expose the seed clearly and avoid hiding global random state changes.

### Debug Path Issues

The current code mixes `data/team_ratings.json` in comments and `team_ratings.json` in implementation. Verify the actual read/write paths before modifying behavior:

- `DataAndRatingAgent.ratings_json` defaults to `team_ratings.json`.
- `MatchSimulationAgent` reads `team_ratings.json`.
- `main.py` prints a message mentioning `data/team_ratings.json`; treat that as text unless the user asks to move the file.

## Quality Bar

Prefer small, local edits. Add tests only when behavior becomes non-trivial or reusable; otherwise verify with direct module or pipeline runs and summarize the command output.
