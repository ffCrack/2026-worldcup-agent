# 2026 World Cup Prediction Agent

A curiosity-driven, AI-assisted project for tracking and predicting the 2026
FIFA World Cup knockout stage.

The project starts from official FIFA ranking points, replays completed
group-stage results, updates team strength with an Elo-style model, projects the
knockout bracket, and displays the current prediction in a local dashboard.

It is designed to be transparent rather than mysterious: model inputs,
generated outputs, news/context adjustments, and update logs are stored as
readable CSV/JSON files.

## Why I Built This

I am not a soccer expert. This project came from curiosity.

When I started working on it, the group stage had already finished. I wanted to
see whether I could use public data and AI coding tools to build a small system
that follows the tournament as it changes:

- completed results update team ratings
- overperforming teams get short-term form credit
- knockout matchups resolve as teams advance
- concrete injury/suspension news can adjust the next match
- the dashboard refreshes as the model changes
- important prediction states can be traced later

This is not a betting model or a professional forecast. It is a learning
project and a demonstration of how AI tools can help build a live, inspectable
sports analytics workflow.

## What The Model Uses

At a high level, the prediction pipeline uses:

- **FIFA ranking points** as the pre-tournament team-strength baseline.
- **Official group-stage results** as completed tournament history.
- **Elo-style updates** after completed matches.
- **Tournament form adjustments** for teams that overperform or underperform
  expectations.
- **FIFA Power Ranking and network-strength adjustments** to capture elite
  player impact and relationships between completed match results.
- **Host-country advantage** for USA, Mexico, and Canada when playing in their
  own country.
- **Knockout advancement logic** that separates 90-minute draw probability from
  the probability of advancing.
- **Concrete post-match context** such as injuries, red cards, suspensions, or
  player availability.
- **Deterministic match intelligence** that turns post-match signals into
  auditable notes and next-match context adjustments.

The implementation details are intentionally simple and inspectable. See
[data/README.md](data/README.md) for data sources, file meanings, and model
assumptions.
This is an agentic workflow rather than an LLM agent: each step is scripted,
logged, and reproducible.

## Current Workflow

The intended workflow is:

```text
FIFA baseline ratings
  -> replay completed group results
  -> update ratings and tournament form
  -> check post-match news after scheduled knockout matches finish
  -> project knockout bracket
  -> apply concrete winner news/context
  -> refresh dashboard
  -> save history when model inputs change
```

The latest bracket prediction is written to:

```text
data/knockout_bracket_predictions.csv
```

The live dashboard reads from the generated CSV outputs.

## Dashboard

The project includes both a static dashboard and a live local dashboard.

### Static Dashboard

Generate a standalone HTML snapshot:

```bash
python3 generate_dashboard.py
```

Then open:

```text
data/dashboard.html
```

### Live Dashboard

Run a local dashboard server:

```bash
python3 live_dashboard.py --interval-minutes 15
```

Then open:

```text
http://127.0.0.1:8765
```

The live dashboard shows:

- projected champion
- projected final
- knockout predictions
- actual results when known
- 90-minute win/draw probabilities
- advancement probabilities
- group-stage history
- run history

It also includes a **Run Update Now** button.

## Main Commands

Run the deterministic prediction pipeline:

```bash
python3 main.py
```

Run automated updates first, then regenerate predictions and dashboard output:

```bash
python3 automate.py
```

Refresh FIFA Power Rankings only:

```bash
python3 refresh_fifa_power_rankings.py
```

Run the live updater without the browser UI:

```bash
python3 live_update.py --interval-minutes 15
```

Generate article charts/screenshots:

```bash
python3 generate_article_assets.py
```

## Important Files

```text
main.py                    Core deterministic prediction pipeline
automate.py                Applies harvested updates, reruns model, refreshes UI
live_dashboard.py          Local live dashboard server
live_update.py             Timed automation loop without UI
generate_dashboard.py      Static dashboard generator
generate_article_assets.py Article visual generator

src/data_agent.py          Rating, form, prediction, and bracket logic
src/automation_agent.py    Match-result and post-match news automation
src/match_intelligence_agent.py Deterministic post-match reasoning layer
src/run_history.py         Historical snapshot recorder
src/data_loader.py         CSV loading helpers

data/                      Inputs, outputs, logs, and data documentation
docs/                      Medium article drafts and article assets
```

## Data Files

Key inputs:

```text
data/pre_tournament_ratings.json
data/world_cup_2026_teams.csv
data/world_cup_history.csv
data/knockout_bracket.csv
data/team_context_adjustments.csv
```

Generated outputs:

```text
data/match_predictions.csv
data/team_form_adjustments.csv
data/team_network_strength.csv
data/team_power_rankings.csv
data/round_of_32_predictions.csv
data/knockout_bracket_predictions.csv
data/high_stakes_predictions.csv
data/dashboard.html
data/team_ratings.json
```

Automation/audit files:

```text
data/automation_sources.csv
data/harvested_match_results.csv
data/news_adjustment_candidates.csv
data/update_log.csv
data/run_history/
```

Timestamped run-history folders are ignored by Git to avoid repository bloat.

## Article Draft

The project also includes a Medium-style article draft:

```text
docs/medium_article_high_level.md
```

Article images are stored in:

```text
docs/assets/
```

## Requirements

The core model uses the Python standard library.

The FIFA Power Rankings refresh uses Playwright because FIFA renders the team
filter and ranking tables in JavaScript. Install it once with:

```bash
python3 -m pip install -r requirements.txt
python3 -m playwright install chromium
```

Recommended Python version: 3.10+

## Notes And Caveats

- This is an experimental project, not a professional forecast.
- The model is intentionally simple and explainable.
- News/context adjustments are rule-based and should be treated as approximate.
- Public data sources can change, so automated harvesting may need maintenance.
- If Playwright is not installed, `automate.py` keeps running but skips/logs the
  FIFA Power Rankings browser refresh and uses the latest saved CSV.
- The dashboard is local-first; it is not currently deployed as a hosted app.

## Repository

GitHub:

```text
https://github.com/ffCrack/2026-worldcup-agent
```
