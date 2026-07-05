import csv
import glob
import os


PREDICTIONS_CSV = "data/knockout_bracket_predictions.csv"
OUTPUT_CSV = "data/prediction_evaluation.csv"


EVALUATION_FIELDS = [
    "round",
    "match_number",
    "date",
    "team1",
    "team2",
    "predicted_advancing_team",
    "actual_advancing_team",
    "evaluation",
    "actual_advance_probability",
    "surprise_score",
    "predicted_90min_result",
    "actual_score",
    "note",
]


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def float_value(value):
    if value in (None, ""):
        return None
    return float(value)


def score(row):
    team1_score = row.get("team1_score_final") or row.get("team1_score_90")
    team2_score = row.get("team2_score_final") or row.get("team2_score_90")
    if team1_score == "" or team2_score == "":
        return ""
    return f"{team1_score}-{team2_score}"


def evaluate_row(row):
    return evaluate_row_against_baseline(row, row)


def evaluate_row_against_baseline(row, baseline):
    actual = row.get("actual_advancing_team", "")
    predicted = baseline.get("predicted_advancing_team", row.get("predicted_advancing_team", ""))
    if not actual:
        return None

    if actual == row.get("team1"):
        actual_probability = float_value(baseline.get("team1_advance_probability", row.get("team1_advance_probability")))
    elif actual == row.get("team2"):
        actual_probability = float_value(baseline.get("team2_advance_probability", row.get("team2_advance_probability")))
    else:
        actual_probability = None

    is_hit = predicted == actual
    surprise = ""
    if actual_probability is not None:
        surprise = round(1 - actual_probability, 4)

    note = "Model hit"
    if not is_hit and actual_probability is not None:
        note = f"Miss: actual winner had {actual_probability * 100:.1f}% pre-match advance probability"
    elif not is_hit:
        note = "Miss: actual winner was not the model pick"

    return {
        "round": row.get("round", ""),
        "match_number": row.get("match_number", ""),
        "date": row.get("date", ""),
        "team1": row.get("team1", ""),
        "team2": row.get("team2", ""),
        "predicted_advancing_team": predicted,
        "actual_advancing_team": actual,
        "evaluation": "Hit" if is_hit else "Miss",
        "actual_advance_probability": "" if actual_probability is None else round(actual_probability, 4),
        "surprise_score": surprise,
        "predicted_90min_result": baseline.get("predicted_90min_result", row.get("predicted_90min_result", "")),
        "actual_score": score(row),
        "note": note,
    }


def pre_result_baselines(history_pattern="data/run_history/*/data/knockout_bracket_predictions.csv"):
    baselines = {}
    for path in sorted(glob.glob(history_pattern)):
        for row in read_csv(path):
            match_number = row.get("match_number", "")
            if not match_number:
                continue
            if row.get("actual_advancing_team"):
                continue
            baselines.setdefault(match_number, []).append(row)
    return baselines


def select_baseline(row, baselines):
    candidates = baselines.get(row.get("match_number", ""), [])
    if not candidates:
        return row

    exact_candidates = [
        candidate for candidate in candidates
        if candidate.get("team1") == row.get("team1") and candidate.get("team2") == row.get("team2")
    ]
    if exact_candidates:
        return exact_candidates[-1]

    same_teams = {row.get("team1"), row.get("team2")}
    same_team_candidates = [
        candidate for candidate in candidates
        if {candidate.get("team1"), candidate.get("team2")} == same_teams
    ]
    if same_team_candidates:
        return same_team_candidates[-1]

    return candidates[0]


def evaluate_predictions(predictions_csv=PREDICTIONS_CSV, output_csv=OUTPUT_CSV):
    baselines = pre_result_baselines()
    rows = [
        evaluation
        for evaluation in (
            evaluate_row_against_baseline(row, select_baseline(row, baselines))
            for row in read_csv(predictions_csv)
        )
        if evaluation is not None
    ]

    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    with open(output_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=EVALUATION_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    return rows


def main():
    rows = evaluate_predictions()
    misses = sum(1 for row in rows if row["evaluation"] == "Miss")
    print(f"[Evaluation]: Wrote {OUTPUT_CSV} with {len(rows)} completed matches; {misses} misses.")


if __name__ == "__main__":
    main()
