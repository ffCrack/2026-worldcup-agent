# 2026 World Cup Prediction Agent

This project predicts the 2026 FIFA World Cup using FIFA ranking points as a
baseline, then updates team strength through match results, tournament form,
host advantage, and concrete post-match availability news.

## What It Does

- Loads real World Cup teams and FIFA baseline ratings.
- Replays completed group-stage matches chronologically.
- Updates Elo-like ratings and short-term tournament form.
- Projects the knockout bracket from Round of 32 through the final.
- Applies concrete injury, suspension, red-card, and availability news as
  transparent team context adjustments.
- Saves run history snapshots when model inputs meaningfully change.
- Provides both static and live dashboards.

## Main Commands

Run the deterministic model pipeline:

```bash
python3 main.py
```

Run automated updates, regenerate predictions, refresh the dashboard, and save
history when needed:

```bash
python3 automate.py
```

Generate the static dashboard:

```bash
python3 generate_dashboard.py
```

Run the live dashboard:

```bash
python3 live_dashboard.py --interval-minutes 15
```

Then open:

```text
http://127.0.0.1:8765
```

## Important Files

- `main.py`: core prediction pipeline.
- `automate.py`: applies harvested updates, reruns the model, refreshes UI.
- `live_dashboard.py`: local live web UI with background updates.
- `generate_dashboard.py`: static dashboard generator.
- `src/data_agent.py`: rating, form, prediction, and bracket logic.
- `src/automation_agent.py`: match-result and post-match news automation.
- `src/run_history.py`: historical snapshot recorder.
- `data/README.md`: data sources, transformations, and model assumptions.

## Data Notes

The `data/` folder contains both model inputs and generated outputs. The most
important input files are:

- `data/pre_tournament_ratings.json`
- `data/world_cup_2026_teams.csv`
- `data/world_cup_history.csv`
- `data/knockout_bracket.csv`
- `data/team_context_adjustments.csv`

Generated outputs include:

- `data/match_predictions.csv`
- `data/team_form_adjustments.csv`
- `data/knockout_bracket_predictions.csv`
- `data/dashboard.html`

Historical run snapshots are stored under `data/run_history/`, but timestamped
snapshot folders are ignored by Git so the repository does not grow too fast.

## GitHub Setup

For a first push to GitHub:

```bash
git init
git remote add origin https://github.com/ffCrack/2026-worldcup-agent.git
git add .
git commit -m "Initial World Cup prediction agent"
git branch -M main
git push -u origin main
```

