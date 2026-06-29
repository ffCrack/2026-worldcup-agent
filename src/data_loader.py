import os
import csv
from datetime import datetime


def _parse_score(value):
    if value is None or value == "":
        return None
    return int(value)


def _parse_optional_int(value):
    if value is None or value == "":
        return None
    return int(value)


def load_world_cup_data(file_path="data/world_cup_history.csv"):
    """
    Loads World Cup match history from a CSV file.
    If the file does not exist, it creates a small starter template file.
    """
    # 1. Check if the file exists. If not, create a starter template!
    if not os.path.exists(file_path):
        print(f"⚠️ {file_path} not found. Creating a starter dataset for you...")

        # Ensure the 'data/' directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Starter mock data (Historical + some recent group stage matches)
        starter_data = {
            "date": ["2022-11-20", "2022-12-18", "2026-06-11", "2026-06-15", "2026-06-18"],
            "home_team": ["Qatar", "Argentina", "Mexico", "USA", "South Africa"],
            "away_team": ["Ecuador", "France", "Canada", "Wales", "South Korea"],
            "home_score": [0, 3, 2, 1, 2],
            "away_score": [2, 3, 1, 1, 1],
            "stage": ["Group Stage", "Final", "Group Stage", "Group Stage", "Group Stage"]
        }

        with open(file_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=starter_data.keys())
            writer.writeheader()
            for row_values in zip(*starter_data.values()):
                writer.writerow(dict(zip(starter_data.keys(), row_values)))
        print(f"✅ Starter dataset saved to {file_path}")

    # 2. Load the CSV file
    print(f"📊 Loading data from {file_path}...")
    with open(file_path, newline="") as f:
        rows = list(csv.DictReader(f))

    # 3. Clean up data types. Scores can be blank for upcoming matches.
    for row in rows:
        row['date'] = datetime.fromisoformat(row['date'])
        row['home_score'] = _parse_score(row.get('home_score'))
        row['away_score'] = _parse_score(row.get('away_score'))

    return rows


def load_world_cup_teams(file_path="data/world_cup_2026_teams.csv"):
    """Loads the real 2026 World Cup participant list and FIFA baseline points."""
    print(f"🌎 Loading World Cup teams from {file_path}...")
    with open(file_path, newline="") as f:
        rows = list(csv.DictReader(f))

    for row in rows:
        row["fifa_rank"] = int(row["fifa_rank"])
        row["fifa_points"] = float(row["fifa_points"])

    return rows


def load_knockout_matches(file_path="data/round_of_32_matches.csv"):
    """Loads knockout fixtures that do not have final scores yet."""
    print(f"🏆 Loading knockout matches from {file_path}...")
    with open(file_path, newline="") as f:
        rows = list(csv.DictReader(f))

    for row in rows:
        row["date"] = datetime.fromisoformat(row["date"])
        row["match_number"] = int(row["match_number"])
        for score_field in (
            "team1_score_90",
            "team2_score_90",
            "team1_score_final",
            "team2_score_final",
        ):
            if score_field in row:
                row[score_field] = _parse_optional_int(row.get(score_field))

    return rows


if __name__ == "__main__":
    # Test the function locally
    match_data = load_world_cup_data()
    print("\n--- Current Match Database ---")
    print(match_data)
