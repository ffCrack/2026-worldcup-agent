# World Cup Model Data Notes

This folder separates model inputs from model outputs so the prediction pipeline
is auditable.

## Inputs

### `pre_tournament_ratings.json`

Official FIFA/Coca-Cola Men's World Ranking points used as the starting Elo-like
baseline before the World Cup.

- Source: FIFA Men's World Ranking, official 11 June 2026 snapshot.
- URL: https://inside.fifa.com/fifa-world-ranking/men?dateId=FRS_Male_Football_20260401
- Transformation: copied the 48 participating teams' FIFA points into a
  team-to-points JSON object.
- Notes: team names follow FIFA naming where possible, for example
  `IR Iran`, `Korea Republic`, `Côte d'Ivoire`, `Cabo Verde`, and `Türkiye`.

### `world_cup_2026_teams.csv`

The 48 participating teams, their groups, FIFA team codes, FIFA ranking, and
FIFA points.

- Source: FIFA World Cup 2026 teams/groups and FIFA Men's World Ranking.
- URLs:
  - https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026
  - https://inside.fifa.com/fifa-world-ranking/men?dateId=FRS_Male_Football_20260401
- Transformation: joined the official 2026 participant/group list to FIFA rank
  and points from the 11 June 2026 ranking snapshot.

### `world_cup_history.csv`

Completed group-stage matches used to update Elo and tournament form.

- Source: FIFA World Cup 2026 fixtures/results article.
- URL: https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/articles/match-schedule-fixtures-results-teams-stadiums
- Transformation: copied each completed group-stage result into one CSV row.
- `home_team` and `away_team` follow FIFA's listed fixture order. For neutral
  World Cup matches, this does not imply home advantage.
- `venue_country` was added from the listed stadium/host city. It is used only
  to give host-country advantage when USA, Mexico, or Canada play in their own
  country.

### `round_of_32_matches.csv`

Official Round of 32 knockout fixtures.

- Source: FIFA World Cup 2026 fixtures/results article.
- URL: https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/articles/match-schedule-fixtures-results-teams-stadiums
- Transformation: copied match number, date, teams, venue, and venue country
  from FIFA's Round of 32 fixture list.

### `knockout_bracket.csv`

The full knockout bracket from Match 73 through Match 104.

- Source: FIFA World Cup 2026 fixtures/results article.
- URL: https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/articles/match-schedule-fixtures-results-teams-stadiums
- Transformation: copied all official knockout match numbers, dates, venues,
  and bracket dependencies.
- For matches whose teams are not known yet, `team1_source` and `team2_source`
  contain values such as `Winner match 74`.
- When a knockout match finishes, update the score columns and
  `actual_advancing_team`.
- If the final score is not known yet but the advancing team is known, fill
  `actual_advancing_team` only. The bracket will advance that team, but Elo will
  not update from that match until score columns are provided.
- Score columns:
  - `team1_score_90`, `team2_score_90`: score after regulation time.
  - `team1_score_final`, `team2_score_final`: score after extra time if needed.
  - Penalty shootout scores should not be placed in these fields; use
    `actual_advancing_team` to record who advanced after penalties.

### `team_context_adjustments.csv`

News/context adjustments for injuries, suspensions, lineup changes, or other
pre-match information not captured by Elo or recent form.

- Source: automatic post-match news collection or manual notes.
- Transformation: one row per team-level adjustment.
- Positive values help a team; negative values hurt a team.
- Automatic news adjustments are applied only to teams that advanced and only
  through that team's next knockout match.
- Example:

```csv
team,adjustment_points,reason,source,active_from,active_until
Brazil,-45,Key forward ruled out with hamstring injury,Reuters,2026-06-29,2026-06-29
Japan,20,Starting midfielder returns from suspension,FIFA,2026-06-29,2026-06-29
```

### `automation_sources.csv`

Configures optional automated data sources.

- `post_match_news_rss`: RSS search source used to collect concrete injury,
  suspension, red-card, and availability news for advancing knockout teams.
- `match_results_csv`: optional normalized CSV URL for match result harvesting.
  This is disabled by default until a reliable normalized source is provided.

### `harvested_match_results.csv`

Normalized match-result input used by `python3 automate.py`.

- If a reliable external feed or manual export writes rows here, automation
  applies those scores/results into `knockout_bracket.csv`.
- Expected columns: `match_number`, score columns, `actual_advancing_team`,
  and `source`.

### `news_adjustment_candidates.csv`

Audit file for post-match news items detected by automation.

- Rows with `status=auto_applied` have already been copied into
  `team_context_adjustments.csv`.
- This file lets you review exactly which news item caused each adjustment.

### `update_log.csv`

Append-only audit trail for automatic input changes.

- Records changed file, match, team, field, old value, new value, source, and
  note.

### `run_history/`

Point-in-time snapshots of the model's important inputs and outputs.

- Created automatically by `python3 automate.py`, `python3 live_update.py`, and
  the live dashboard server.
- Each run gets a timestamped folder containing copied input/output files and a
  `manifest.json`.
- `run_history/index.csv` summarizes all recorded runs, including projected
  champion and how many automated updates were applied.
- To avoid noisy history during frequent live checks, snapshots are saved when
  match results or news adjustments change the model inputs. If nothing changes,
  only one daily checkpoint is saved.

## Outputs

### `match_predictions.csv`

Generated by `python3 main.py`.

Contains pre-match Elo, form/context adjustments, 90-minute probabilities,
actual scores, actual result, and post-match Elo for group-stage matches.

### `team_form_adjustments.csv`

Generated by `python3 main.py`.

Summarizes which teams are overperforming or underperforming expectation after
the processed matches.

### `round_of_32_predictions.csv`

Generated by `python3 main.py`.

Contains Round of 32 90-minute probabilities and advancement probabilities.
Knockout matches can draw after 90 minutes, so the file separates:

- `predicted_90min_result`
- `predicted_advancing_team`

### `knockout_bracket_predictions.csv`

Generated by `python3 main.py`.

Projects the entire knockout path from Round of 32 through the final. Actual
advancing teams in `knockout_bracket.csv` override model predictions. Unknown
future slots are filled from current projected winners.

### `dashboard.html`

Generated by `python3 generate_dashboard.py` or automatically by
`python3 automate.py`.

Shows knockout predictions, actual results, group-stage history, and run
history in a browser-readable dashboard.

## Current Model Assumptions

- FIFA ranking points are used as the baseline rating scale.
- World Cup group-stage Elo update weight is `50`.
- FIFA-style expected score scale uses divisor `600`.
- Host advantage is `+75` rating points only when USA, Mexico, or Canada play
  in their own country.
- Tournament form is a decayed over/under-performance adjustment:
  `form = previous_form * 0.65 + (actual_score - expected_score)`.
- Form is converted to rating points with multiplier `90`.
- Draw probability is highest when adjusted ratings are close and decreases as
  rating gap grows.

## Reproducibility

Run:

```bash
python3 main.py
```

This regenerates:

- `match_predictions.csv`
- `team_form_adjustments.csv`
- `team_ratings.json`
- `round_of_32_predictions.csv`
- `knockout_bracket_predictions.csv`

To refresh the dashboard from current output CSVs, run:

```bash
python3 generate_dashboard.py
```

Automated runs save a historical snapshot under `data/run_history/` only when
model inputs changed, or once per day as a checkpoint.

To harvest automated updates first, then regenerate predictions, run:

```bash
python3 automate.py
```

To keep the model checking for updates during match windows, run:

```bash
python3 live_update.py --interval-minutes 15
```

This repeats the automation pipeline until you stop it with `Ctrl+C`.

To run a browser UI that refreshes itself and also runs automated updates in
the background, run:

```bash
python3 live_dashboard.py --interval-minutes 15
```

Then open `http://127.0.0.1:8765`.
