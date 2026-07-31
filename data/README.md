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
- `kickoff_utc` is the scheduled start time when known.
- `result_check_after_utc` is the fixed automation time for checking post-match
  news, normally kickoff plus 150 minutes.
- The source files keep these timestamps in UTC for consistency. The dashboard
  converts them to `America/Los_Angeles` when displayed.
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

### `prediction_locks.csv`

Optional audit file for the exact pre-result prediction used to evaluate a
match.

- Source: dashboard output or user-confirmed prediction before the result is
  entered.
- Transformation: one row per match number with the predicted advancing team
  and advance probabilities shown before the match result was known.
- Evaluation priority: `prediction_locks.csv` is used first, then historical
  run-history snapshots, then the current prediction row as a fallback.

### `player_scores.csv`

Optional player-level squad strength input.

- Source: FIFA player/squad score pages or configured official FIFA
  player-score endpoints. The automation refreshes this file before upcoming
  matches when a FIFA source URL is configured in `automation_sources.csv`.
- Expected columns:
  - `team`: team name matching the rest of the project.
  - `player`: player name.
  - `position`: optional position label such as GK, DEF, MID, FWD.
  - `score`: numeric player score.
  - `role`: use `starter` for expected starting XI players. If fewer than 7
    starters are marked, the model uses the top 11 available players.
  - `status`: leave blank for available players; use `out`, `injured`,
    `suspended`, or `unavailable` to exclude a player from the squad score.
  - `source`: URL or note for where the score came from.
- Model transformation:
  - starting XI average receives 85% weight.
  - bench/depth average receives 15% weight.
  - team squad strength is compared with the average of teams that have player
    data.
  - each player-score point above/below that baseline becomes 8 Elo-like points,
    capped at +/-80.

### `player_score_refresh_log.csv`

Audit log for pre-match FIFA player-score refreshes.

- The automation checks matches whose `kickoff_utc` is within the next 24 hours.
- If no FIFA player-score URL is configured, the check is logged as `skipped`.
- If a FIFA URL is configured but no numeric player scores are found, the check
  is logged as `no_scores_found`.
- Only real numeric rows found in the configured FIFA source are written into
  `player_scores.csv`.

### `fifa_power_rankings.csv`

Official FIFA Power Rankings powered by Aramco player-performance input.

- Source: https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/power-rankings
- The page provides objective player scores from World Cup match data.
- Expected columns:
  - `rank`: FIFA player ranking position within the visible category.
  - `change`: movement shown by FIFA when available.
  - `player`: player name as shown by FIFA.
  - `team`: national team.
  - `attacking`, `creativity`, `defending`: outfield player category scores.
  - `goalkeeping_defending`, `goalkeeping_possession`: goalkeeper category
    scores.
  - `overall_score`: transparent project score used by the model. For outfield
    players, this is the average of attacking, creativity, and defending. For
    goalkeepers, this is the available goalkeeper score average.
  - `source`: FIFA page URL.
  - `checked_at`: when the row was observed.
- Model transformation:
  - team power score is the average of up to the top 3 ranked players per team.
  - teams absent from the file receive no power-ranking adjustment.
  - scores only apply to matches on or after the row's `checked_at` date, so
    newer rankings do not rewrite old pre-match evaluations.
  - each team-power point above/below the active baseline becomes 20 Elo-like
    points.
  - top-10 ranked players add a rank bonus.
  - the total power-ranking adjustment is capped at +/-100.
- Refresh:
  - `refresh_fifa_power_rankings.py` opens the FIFA page in a browser, selects
    each current Round of 16 team from the team filter, reads both the Outfield
    and Goalkeeper tables, concatenates the rows, and rewrites this CSV.
  - `automate.py` calls that script before rerunning the model when
    `fifa_power_rankings_browser` is enabled in `automation_sources.csv`.
  - The browser refresh requires Playwright and Chromium.

### `team_power_rankings.csv`

Generated output summarizing how `fifa_power_rankings.csv` affects each team.

### `team_network_strength.csv`

Generated relationship-strength output from completed group and knockout
matches.

- Source: `world_cup_history.csv` plus completed rows in `knockout_bracket.csv`.
- Transformation:
  - each completed match is an edge between two teams.
  - teams receive direct credit for beating, drawing, or narrowly losing to
    strong opponents relative to FIFA baseline expectation.
  - strength propagates through opponents for several iterations, so results
    such as `A beats B` and `B beats C` increase confidence that `A` is strong.
  - the network score is converted into Elo-like points and capped at +/-100.

### `fifa_power_rankings_harvest.json`

Raw browser-harvest audit file from the latest FIFA Power Rankings refresh.
This preserves the unnormalized table rows before conversion into
`fifa_power_rankings.csv`.

### `fifa_power_ranking_refresh_log.csv`

Audit log for automated FIFA Power Rankings refresh attempts.

- `applied`: browser refresh completed and changed `fifa_power_rankings.csv`.
- `unchanged`: browser refresh completed but the normalized CSV was unchanged.
- `failed`: browser refresh could not run, commonly because Playwright or the
  Chromium browser is not installed.

### `automation_sources.csv`

Configures optional automated data sources.

- `post_match_news_rss`: RSS search source used to collect concrete injury,
  suspension, red-card, and availability news for advancing knockout teams.
- `match_results_csv`: optional normalized CSV URL for match result harvesting.
  This is disabled by default until a reliable normalized source is provided.
- `fifa_player_scores_json`: official FIFA JSON or FIFA page URL used for
  player-score refreshes before upcoming matches. URL templates may use
  `{match_number}`, `{team1}`, and `{team2}`.
- `fifa_power_rankings_browser`: official FIFA Power Rankings page used by the
  browser refresh script.

### `harvested_match_results.csv`

Normalized match-result input used by `python3 automate.py`.

- If a reliable external feed or manual export writes rows here, automation
  applies those scores/results into `knockout_bracket.csv`.
- Expected columns: `match_number`, score columns, `actual_advancing_team`,
  and `source`.

### `result_check_schedule.csv`

Backup schedule for news-based result harvesting.

- `kickoff_utc` is the match kickoff time.
- `check_after_utc` is when automation is allowed to check post-match news.
  For knockout games this is set to kickoff plus 150 minutes, so extra time and
  penalties usually have room to finish.
- The bracket file carries the active `kickoff_utc` and
  `result_check_after_utc` fields. This file is kept as a transparent source and
  fallback.

### `news_adjustment_candidates.csv`

Audit file for post-match news items detected by automation.

- Rows with `status=auto_applied` have already been copied into
  `team_context_adjustments.csv`.
- This file lets you review exactly which news item caused each adjustment.

### `match_intelligence_notes.csv`

Generated by the deterministic match-intelligence agent.

- Source: completed rows in `knockout_bracket_predictions.csv`.
- Purpose: captures the project’s agentic "second brain" reasoning after each
  completed knockout match.
- This is not an LLM agent. It uses transparent rules based on score margin,
  penalty advancement, pre-match probability, model upset, and consecutive hard
  wins.
- Rows include match/result, pre-result prediction/probability, detected
  signals, and any proposed team context adjustment.
- If a note creates a context adjustment, the reason starts with
  `Match intelligence after Match ...` in `team_context_adjustments.csv`.

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

### `high_stakes_predictions.csv`

Generated by `python3 generate_high_stakes_predictions.py` or automatically by
`python3 automate.py`.

Separate semi-final/final-stage ensemble model. It starts with the main
knockout advancement probability, then reweights late-tournament signals:

- adjusted Elo gap
- recent World Cup form from this tournament only
- FIFA power-ranking/star-player gap
- result-network strength gap
- rest and extra-time fatigue
- knockout pressure/resilience from completed knockout matches
- coach/strategy fit from `high_stakes_strategy_profiles.csv`
- late-game clutch tendency from `high_stakes_strategy_profiles.csv`

This is not a betting-odds feed. It is a transparent model view designed to make
critical-match assumptions easier to inspect.

### `high_stakes_strategy_profiles.csv`

Manual/source-backed tactical profile for late knockout matches.

- `team` and `opponent` identify the matchup.
- `strategy_score` is an Elo-like tactical/coach-fit adjustment used only by the
  high-stakes model.
- `late_game_score` is an Elo-like adjustment for repeated late-game resilience,
  comeback threat, and end-of-match finishing.
- `reason` explains the tactical signal.
- `source` records where the profile came from.

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
- Network strength is learned from completed tournament matches and converted
  to rating points with multiplier `115`, capped at +/-100.
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
- `team_network_strength.csv`
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
