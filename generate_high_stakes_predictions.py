import csv
import math
import os
from datetime import date


INPUT_PREDICTIONS = "data/knockout_bracket_predictions.csv"
GROUP_HISTORY = "data/world_cup_history.csv"
STRATEGY_PROFILES = "data/high_stakes_strategy_profiles.csv"
OUTPUT_PATH = "data/high_stakes_predictions.csv"

HIGH_STAKES_ROUNDS = {"Semi-final", "Bronze final", "Final"}

FIELDS = [
    "round",
    "match_number",
    "date",
    "team1",
    "team2",
    "base_team1_advance_probability",
    "base_team2_advance_probability",
    "high_stakes_team1_advance_probability",
    "high_stakes_team2_advance_probability",
    "high_stakes_pick",
    "confidence",
    "feature_probability_team1",
    "baseline_model_weight",
    "adjusted_elo_gap",
    "recent_world_cup_form_gap",
    "knockout_form_gap",
    "defensive_control_gap",
    "star_power_gap",
    "network_gap",
    "fatigue_gap",
    "pressure_gap",
    "strategy_gap",
    "clutch_late_game_gap",
    "team1_recent_form",
    "team2_recent_form",
    "team1_knockout_form",
    "team2_knockout_form",
    "team1_defensive_control",
    "team2_defensive_control",
    "team1_strategy_score",
    "team2_strategy_score",
    "team1_clutch_late_game_score",
    "team2_clutch_late_game_score",
    "team1_fatigue_adjustment",
    "team2_fatigue_adjustment",
    "rationale",
]

BASELINE_MODEL_WEIGHT = 0.15


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def profile_key(team, opponent=""):
    return (team.strip().lower(), opponent.strip().lower())


def build_strategy_profiles(rows):
    profiles = {}
    for row in rows:
        team = row.get("team", "")
        opponent = row.get("opponent", "")
        if not team:
            continue
        profiles[profile_key(team, opponent)] = row
    return profiles


def float_value(value, default=0.0):
    try:
        if value in (None, ""):
            return default
        return float(value)
    except ValueError:
        return default


def int_value(value):
    try:
        if value in (None, ""):
            return None
        return int(float(value))
    except ValueError:
        return None


def clamp(value, low, high):
    return max(low, min(high, value))


def logistic_from_gap(gap, scale=380):
    return 1 / (1 + 10 ** (-gap / scale))


def logit_probability(probability, scale=380):
    probability = clamp(probability, 0.01, 0.99)
    return scale * math.log10(probability / (1 - probability))


def match_date(row):
    try:
        return date.fromisoformat(row.get("date", ""))
    except ValueError:
        return None


def score_for_team(team, team1, team2, score1, score2, advancing_team="", knockout=False):
    if score1 is None or score2 is None:
        return None
    if team == team1:
        goals_for, goals_against = score1, score2
    elif team == team2:
        goals_for, goals_against = score2, score1
    else:
        return None

    goal_diff = goals_for - goals_against
    if goal_diff > 0:
        result_points = 1.0
    elif goal_diff == 0:
        result_points = 0.5
    else:
        result_points = 0.0

    if knockout and advancing_team == team and goal_diff <= 0:
        result_points = 0.62

    return result_points + clamp(goal_diff, -3, 3) * 0.10


def build_team_results(group_rows, knockout_rows):
    results = {}

    for row in group_rows:
        team1 = row.get("home_team", "")
        team2 = row.get("away_team", "")
        score1 = int_value(row.get("home_score"))
        score2 = int_value(row.get("away_score"))
        played_on = match_date(row)
        for team in (team1, team2):
            value = score_for_team(team, team1, team2, score1, score2)
            if value is None:
                continue
            results.setdefault(team, []).append({
                "date": played_on,
                "round": row.get("stage", ""),
                "score": value,
                "score1": score1,
                "score2": score2,
                "team1": team1,
                "team2": team2,
                "knockout": False,
                "advanced": "",
                "went_extra": False,
            })

    for row in knockout_rows:
        if row.get("is_actual_result") != "True":
            continue
        team1 = row.get("team1", "")
        team2 = row.get("team2", "")
        score1 = int_value(row.get("team1_score_final")) if row.get("team1_score_final") else int_value(row.get("team1_score_90"))
        score2 = int_value(row.get("team2_score_final")) if row.get("team2_score_final") else int_value(row.get("team2_score_90"))
        went_extra = bool(row.get("team1_score_final") or row.get("team2_score_final"))
        advanced = row.get("actual_advancing_team", "")
        played_on = match_date(row)
        for team in (team1, team2):
            value = score_for_team(team, team1, team2, score1, score2, advanced, knockout=True)
            if value is None:
                continue
            results.setdefault(team, []).append({
                "date": played_on,
                "round": row.get("round", ""),
                "score": value + (0.08 if advanced == team else 0.0),
                "score1": score1,
                "score2": score2,
                "team1": team1,
                "team2": team2,
                "knockout": True,
                "advanced": advanced,
                "went_extra": went_extra,
            })

    for team_rows in results.values():
        team_rows.sort(key=lambda item: (item["date"] or date.min, item["round"]))
    return results


def recent_form(team, team_results):
    rows = team_results.get(team, [])[-5:]
    if not rows:
        return 50.0
    weighted_total = 0.0
    weight_sum = 0.0
    for index, item in enumerate(rows, start=1):
        weight = index
        weighted_total += item["score"] * weight
        weight_sum += weight
    return round((weighted_total / weight_sum) * 100, 1)


def knockout_form(team, team_results):
    rows = [row for row in team_results.get(team, []) if row["knockout"]][-4:]
    if not rows:
        return recent_form(team, team_results)
    weighted_total = 0.0
    weight_sum = 0.0
    for index, item in enumerate(rows, start=1):
        weight = index * 1.5
        weighted_total += item["score"] * weight
        weight_sum += weight
    return round((weighted_total / weight_sum) * 100, 1)


def defensive_control(team, team_results):
    rows = team_results.get(team, [])[-5:]
    if not rows:
        return 50.0

    total = 0.0
    weight_sum = 0.0
    for index, row in enumerate(rows, start=1):
        if row["team1"] == team:
            goals_for = row["score1"] or 0
            goals_against = row["score2"] or 0
        else:
            goals_for = row["score2"] or 0
            goals_against = row["score1"] or 0

        clean_sheet_bonus = 22 if goals_against == 0 else 0
        concession_penalty = goals_against * 12
        control = 70 + clean_sheet_bonus + clamp(goals_for - goals_against, -3, 3) * 6 - concession_penalty
        if row["knockout"]:
            control += 6
        weight = index
        total += control * weight
        weight_sum += weight
    return round(clamp(total / weight_sum, 0, 140), 1)


def pressure_score(team, team_results):
    rows = [row for row in team_results.get(team, []) if row["knockout"]]
    if not rows:
        return 0.0
    knockout_wins = sum(1 for row in rows if row["advanced"] == team)
    margins = []
    for row in rows:
        if row["team1"] == team:
            margins.append((row["score1"] or 0) - (row["score2"] or 0))
        else:
            margins.append((row["score2"] or 0) - (row["score1"] or 0))
    average_margin = sum(margins) / len(margins)
    return round(knockout_wins * 5 + clamp(average_margin, -2, 2) * 4, 1)


def strategy_score(team, opponent, strategy_profiles):
    row = (
        strategy_profiles.get(profile_key(team, opponent))
        or strategy_profiles.get(profile_key(team, ""))
        or {}
    )
    return float_value(row.get("strategy_score"), 0.0)


def clutch_late_game_score(team, opponent, strategy_profiles):
    row = (
        strategy_profiles.get(profile_key(team, opponent))
        or strategy_profiles.get(profile_key(team, ""))
        or {}
    )
    return float_value(row.get("late_game_score"), 0.0)


def fatigue_adjustment(team, match_row, team_results):
    rows = team_results.get(team, [])
    if not rows:
        return 0.0
    upcoming = match_date(match_row)
    last = rows[-1]
    adjustment = 0.0
    if last["went_extra"]:
        adjustment -= 10.0
    if upcoming and last["date"]:
        rest_days = (upcoming - last["date"]).days
        if rest_days <= 3:
            adjustment -= 8.0
        elif rest_days == 4:
            adjustment -= 4.0
        elif rest_days >= 6:
            adjustment += 3.0
    return adjustment


def confidence_label(probability):
    edge = abs(probability - 0.5)
    if edge < 0.04:
        return "Toss-up"
    if edge < 0.10:
        return "Lean"
    if edge < 0.18:
        return "Moderate"
    return "Strong"


def rationale(row, pick, feature_values):
    strongest = sorted(
        feature_values.items(),
        key=lambda item: abs(item[1]),
        reverse=True,
    )[:3]
    parts = [f"{name} {value:+.1f}" for name, value in strongest if abs(value) >= 1]
    if not parts:
        return f"{pick} by blended high-stakes model; no single feature dominates."
    return f"{pick} by blended high-stakes model; key edges: " + ", ".join(parts) + "."


def high_stakes_row(row, team_results, strategy_profiles):
    team1 = row["team1"]
    team2 = row["team2"]
    base_team1 = float_value(row.get("team1_advance_probability"), 0.5)
    base_team2 = float_value(row.get("team2_advance_probability"), 0.5)

    adjusted_elo_gap = float_value(row.get("team1_adjusted_elo")) - float_value(row.get("team2_adjusted_elo"))
    team1_form = recent_form(team1, team_results)
    team2_form = recent_form(team2, team_results)
    team1_knockout_form = knockout_form(team1, team_results)
    team2_knockout_form = knockout_form(team2, team_results)
    team1_defensive_control = defensive_control(team1, team_results)
    team2_defensive_control = defensive_control(team2, team_results)
    team1_strategy = strategy_score(team1, team2, strategy_profiles)
    team2_strategy = strategy_score(team2, team1, strategy_profiles)
    team1_clutch = clutch_late_game_score(team1, team2, strategy_profiles)
    team2_clutch = clutch_late_game_score(team2, team1, strategy_profiles)
    recent_form_gap = (team1_form - team2_form) * 2.0
    knockout_form_gap = (team1_knockout_form - team2_knockout_form) * 2.5
    defensive_control_gap = (team1_defensive_control - team2_defensive_control) * 1.8
    star_power_gap = float_value(row.get("team1_power_adjustment")) - float_value(row.get("team2_power_adjustment"))
    network_gap = float_value(row.get("team1_network_adjustment")) - float_value(row.get("team2_network_adjustment"))
    team1_fatigue = fatigue_adjustment(team1, row, team_results)
    team2_fatigue = fatigue_adjustment(team2, row, team_results)
    fatigue_gap = team1_fatigue - team2_fatigue
    pressure_gap = pressure_score(team1, team_results) - pressure_score(team2, team_results)
    strategy_gap = team1_strategy - team2_strategy
    clutch_gap = team1_clutch - team2_clutch

    feature_values = {
        "adjusted Elo": adjusted_elo_gap,
        "recent World Cup form": recent_form_gap,
        "knockout form": knockout_form_gap,
        "defensive control": defensive_control_gap,
        "star/player power": star_power_gap,
        "result network": network_gap,
        "fatigue/rest": fatigue_gap,
        "knockout pressure": pressure_gap,
        "coach/strategy fit": strategy_gap,
        "late-game clutch": clutch_gap,
    }

    feature_gap = (
        0.12 * adjusted_elo_gap
        + 0.22 * recent_form_gap
        + 0.28 * knockout_form_gap
        + 0.18 * defensive_control_gap
        + 0.14 * star_power_gap
        + 0.08 * network_gap
        + 0.08 * pressure_gap
        + 0.24 * strategy_gap
        + 0.30 * clutch_gap
        + fatigue_gap
    )
    feature_probability = logistic_from_gap(feature_gap)

    base_gap = logit_probability(base_team1)
    blended_gap = (
        BASELINE_MODEL_WEIGHT * base_gap
        + (1 - BASELINE_MODEL_WEIGHT) * logit_probability(feature_probability)
    )
    high_team1 = clamp(logistic_from_gap(blended_gap), 0.03, 0.97)
    high_team2 = 1 - high_team1
    pick = team1 if high_team1 >= high_team2 else team2

    return {
        "round": row.get("round", ""),
        "match_number": row.get("match_number", ""),
        "date": row.get("date", ""),
        "team1": team1,
        "team2": team2,
        "base_team1_advance_probability": round(base_team1, 4),
        "base_team2_advance_probability": round(base_team2, 4),
        "high_stakes_team1_advance_probability": round(high_team1, 4),
        "high_stakes_team2_advance_probability": round(high_team2, 4),
        "high_stakes_pick": pick,
        "confidence": confidence_label(high_team1),
        "feature_probability_team1": round(feature_probability, 4),
        "baseline_model_weight": BASELINE_MODEL_WEIGHT,
        "adjusted_elo_gap": round(adjusted_elo_gap, 1),
        "recent_world_cup_form_gap": round(recent_form_gap, 1),
        "knockout_form_gap": round(knockout_form_gap, 1),
        "defensive_control_gap": round(defensive_control_gap, 1),
        "star_power_gap": round(star_power_gap, 1),
        "network_gap": round(network_gap, 1),
        "fatigue_gap": round(fatigue_gap, 1),
        "pressure_gap": round(pressure_gap, 1),
        "strategy_gap": round(strategy_gap, 1),
        "clutch_late_game_gap": round(clutch_gap, 1),
        "team1_recent_form": team1_form,
        "team2_recent_form": team2_form,
        "team1_knockout_form": team1_knockout_form,
        "team2_knockout_form": team2_knockout_form,
        "team1_defensive_control": team1_defensive_control,
        "team2_defensive_control": team2_defensive_control,
        "team1_strategy_score": round(team1_strategy, 1),
        "team2_strategy_score": round(team2_strategy, 1),
        "team1_clutch_late_game_score": round(team1_clutch, 1),
        "team2_clutch_late_game_score": round(team2_clutch, 1),
        "team1_fatigue_adjustment": round(team1_fatigue, 1),
        "team2_fatigue_adjustment": round(team2_fatigue, 1),
        "rationale": rationale(row, pick, feature_values),
    }


def generate_high_stakes_predictions():
    knockout_rows = read_csv(INPUT_PREDICTIONS)
    group_rows = read_csv(GROUP_HISTORY)
    strategy_profiles = build_strategy_profiles(read_csv(STRATEGY_PROFILES))
    team_results = build_team_results(group_rows, knockout_rows)
    rows = [
        high_stakes_row(row, team_results, strategy_profiles)
        for row in knockout_rows
        if row.get("round") in HIGH_STAKES_ROUNDS
        and row.get("is_actual_result") != "True"
        and row.get("team1")
        and row.get("team2")
    ]
    write_csv(OUTPUT_PATH, rows)
    return rows


def main():
    rows = generate_high_stakes_predictions()
    print(f"[High Stakes Model]: Wrote {OUTPUT_PATH} ({len(rows)} rows).")


if __name__ == "__main__":
    main()
