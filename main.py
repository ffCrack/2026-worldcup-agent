from src.data_loader import (
    load_knockout_matches,
    load_world_cup_data,
    load_world_cup_teams,
)
from src.data_agent import DataAndRatingAgent


def main():
    print("=== STARTING AGENTIC WORLD CUP PIPELINE ===")

    # 1. Load the real 2026 participant list and FIFA baseline points.
    world_cup_teams = load_world_cup_teams("data/world_cup_2026_teams.csv")
    participating_teams = [row["team"] for row in world_cup_teams]
    print(f"[Team Data]: Loaded {len(participating_teams)} World Cup teams.")

    # 2. Load match data. Completed matches update Elo; blank scores are predicted only.
    match_df = load_world_cup_data("data/world_cup_history.csv")

    # 3. Initialize the Data & Rating Agent using the official FIFA baseline.
    rating_agent = DataAndRatingAgent(
        history_csv_path="data/world_cup_history.csv",
        ratings_json="team_ratings.json",
        seed_ratings_json="data/pre_tournament_ratings.json",
        context_adjustments_csv="data/team_context_adjustments.csv",
    )

    # 4. Predict every match from the Elo state available before the match,
    # then update Elo only after completed match results.
    print("\n[Data Agent]: Predicting matches and updating Elo chronologically...")
    predictions_df = rating_agent.process_matches_chronologically(match_df)
    rating_agent.save_predictions(predictions_df)
    rating_agent.save_form_summary()
    rating_agent.save_ratings()
    print("[Data Agent]: 'data/match_predictions.csv' written successfully.")
    print("[Data Agent]: 'data/team_form_adjustments.csv' written successfully.")
    print("[Data Agent]: 'team_ratings.json' updated successfully.")

    # 5. Predict the full knockout bracket. Actual results in the bracket file
    # override model predictions; future slots use projected advancing teams.
    print("\n[Knockout Agent]: Predicting full knockout bracket...")
    knockout_matches = load_knockout_matches("data/knockout_bracket.csv")
    knockout_predictions = rating_agent.predict_knockout_bracket(knockout_matches)
    rating_agent.save_knockout_predictions(
        knockout_predictions,
        file_path="data/knockout_bracket_predictions.csv",
    )
    round_of_32_predictions = [
        row for row in knockout_predictions
        if row["round"] == "Round of 32"
    ]
    rating_agent.save_knockout_predictions(round_of_32_predictions)
    rating_agent.save_ratings()
    print("[Knockout Agent]: 'data/round_of_32_predictions.csv' written successfully.")
    print("[Knockout Agent]: 'data/knockout_bracket_predictions.csv' written successfully.")


if __name__ == "__main__":
    main()
