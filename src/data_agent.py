import json
import os
import csv
import math


class DataAndRatingAgent:
    HOST_COUNTRIES = {
        "Canada": "Canada",
        "Mexico": "Mexico",
        "USA": "USA",
    }

    def __init__(
        self,
        history_csv_path="world_cup_history.csv",
        ratings_json="team_ratings.json",
        seed_ratings_json=None,
        context_adjustments_csv="data/team_context_adjustments.csv",
    ):
        self.csv_path = history_csv_path
        self.ratings_json = ratings_json
        self.k_factor = 50  # FIFA uses 50 for World Cup matches before the quarter-finals.
        self.elo_scale = 600
        self.home_advantage_points = 75
        self.max_draw_probability = 0.36
        self.draw_decay = 600
        self.form_decay = 0.65
        self.form_points = 90
        self.form = {}
        self.context_adjustments = self.load_context_adjustments(context_adjustments_csv)

        # Start from a pre-tournament ratings file if one is provided.
        # Otherwise, unseen teams begin at the default 1500 Elo baseline.
        if seed_ratings_json and os.path.exists(seed_ratings_json):
            with open(seed_ratings_json, 'r') as f:
                self.ratings = json.load(f)
        else:
            self.ratings = {}

    def get_rating(self, team):
        # Default baseline rating for a World Cup level team is 1500
        return self.ratings.get(team, 1500.0)

    def host_advantage(self, team, venue_country):
        """Applies a modest boost only when a 2026 host plays in its own country."""
        if self.HOST_COUNTRIES.get(team) == venue_country:
            return self.home_advantage_points
        return 0

    def form_adjustment(self, team):
        """Temporary tournament-form boost from recent over/under-performance."""
        return self.form.get(team, 0.0) * self.form_points

    def load_context_adjustments(self, file_path):
        """Loads manual news/context adjustments such as injuries or suspensions."""
        if not file_path or not os.path.exists(file_path):
            return []

        with open(file_path, newline="") as f:
            rows = list(csv.DictReader(f))

        adjustments = []
        for row in rows:
            if not row.get("team") or not row.get("adjustment_points"):
                continue

            adjustments.append({
                "team": row["team"],
                "adjustment_points": float(row["adjustment_points"]),
                "reason": row.get("reason", ""),
                "source": row.get("source", ""),
                "active_from": row.get("active_from", ""),
                "active_until": row.get("active_until", ""),
            })

        return adjustments

    def context_adjustment(self, team, match_date=None):
        total = 0.0
        for row in self.context_adjustments:
            if row["team"] != team:
                continue
            if not self.context_adjustment_is_active(row, match_date):
                continue
            total += row["adjustment_points"]

        return total

    def context_adjustment_reasons(self, team, match_date=None):
        reasons = []
        for row in self.context_adjustments:
            if row["team"] != team:
                continue
            if not self.context_adjustment_is_active(row, match_date):
                continue
            reason = row["reason"]
            if row["source"]:
                reason = f"{reason} ({row['source']})"
            reasons.append(reason)

        return " | ".join(reason for reason in reasons if reason)

    def context_adjustment_is_active(self, adjustment, match_date):
        if not match_date:
            return True
        if hasattr(match_date, "date"):
            match_date = match_date.date().isoformat()

        active_from = adjustment.get("active_from", "")
        active_until = adjustment.get("active_until", "")
        if active_from and match_date < active_from:
            return False
        if active_until and match_date > active_until:
            return False
        return True

    def adjusted_rating(self, team, venue_country, match_date=None):
        return (
            self.get_rating(team)
            + self.host_advantage(team, venue_country)
            + self.form_adjustment(team)
            + self.context_adjustment(team, match_date)
        )

    def expected_score(self, team1, team2, venue_country=None, match_date=None):
        """Returns team1's Elo expected score before a match."""
        r1 = self.adjusted_rating(team1, venue_country, match_date)
        r2 = self.adjusted_rating(team2, venue_country, match_date)
        return 1 / (1 + 10 ** ((r2 - r1) / self.elo_scale))

    def predict_match(self, team1, team2, venue_country=None, match_date=None):
        """Predicts a match using ratings available before that match."""
        team1_rating = self.get_rating(team1)
        team2_rating = self.get_rating(team2)
        team1_context = self.context_adjustment(team1, match_date)
        team2_context = self.context_adjustment(team2, match_date)
        team1_adjusted = self.adjusted_rating(team1, venue_country, match_date)
        team2_adjusted = self.adjusted_rating(team2, venue_country, match_date)
        expected = self.expected_score(team1, team2, venue_country, match_date)
        rating_gap = abs(team1_adjusted - team2_adjusted)

        draw_prob = self.max_draw_probability * math.exp(-rating_gap / self.draw_decay)
        home_win_prob = max(0, expected - (draw_prob / 2))
        away_win_prob = max(0, (1 - expected) - (draw_prob / 2))
        total_prob = home_win_prob + draw_prob + away_win_prob

        home_win_prob /= total_prob
        draw_prob /= total_prob
        away_win_prob /= total_prob

        outcomes = [
            (team1, home_win_prob),
            ("Draw", draw_prob),
            (team2, away_win_prob),
        ]
        predicted_result = max(outcomes, key=lambda item: item[1])[0]

        return {
            "home_pre_elo": round(team1_rating, 1),
            "away_pre_elo": round(team2_rating, 1),
            "home_form_adjustment": round(self.form_adjustment(team1), 1),
            "away_form_adjustment": round(self.form_adjustment(team2), 1),
            "home_context_adjustment": round(team1_context, 1),
            "away_context_adjustment": round(team2_context, 1),
            "home_context_reason": self.context_adjustment_reasons(team1, match_date),
            "away_context_reason": self.context_adjustment_reasons(team2, match_date),
            "home_adjusted_elo": round(team1_adjusted, 1),
            "away_adjusted_elo": round(team2_adjusted, 1),
            "home_advantage_team": self.get_home_advantage_team(team1, team2, venue_country),
            "home_win_probability": round(home_win_prob, 4),
            "draw_probability": round(draw_prob, 4),
            "away_win_probability": round(away_win_prob, 4),
            "predicted_result": predicted_result,
            "predicted_winner": predicted_result,
        }

    def get_home_advantage_team(self, team1, team2, venue_country):
        if self.host_advantage(team1, venue_country):
            return team1
        if self.host_advantage(team2, venue_country):
            return team2
        return ""

    def get_actual_winner(self, team1, team2, score1, score2):
        """Returns the actual match winner from the final score."""
        if score1 is None or score2 is None:
            return ""
        if score1 > score2:
            return team1
        if score2 > score1:
            return team2
        return "Draw"

    def update_elo(self, team1, team2, score1, score2, venue_country=None, match_date=None):
        r1 = self.get_rating(team1)
        r2 = self.get_rating(team2)

        # Expected scores based on current ratings
        exp1 = self.expected_score(team1, team2, venue_country, match_date)
        exp2 = 1 - exp1

        # Actual scores
        if score1 > score2:
            act1, act2 = 1.0, 0.0
        elif score2 > score1:
            act1, act2 = 0.0, 1.0
        else:
            act1, act2 = 0.5, 0.5

        # Update ratings
        self.ratings[team1] = round(r1 + self.k_factor * (act1 - exp1), 1)
        self.ratings[team2] = round(r2 + self.k_factor * (act2 - exp2), 1)
        self.update_form(team1, act1 - exp1)
        self.update_form(team2, act2 - exp2)

    def update_form(self, team, surprise):
        """Tracks short-term form as decayed performance above/below expectation."""
        previous = self.form.get(team, 0.0)
        self.form[team] = (previous * self.form_decay) + surprise

    def process_matches_chronologically(self, df):
        """
        Predicts each match from the pre-match Elo state, then updates Elo
        with the final score when a result is available.
        """
        predictions = []
        sorted_matches = sorted(df, key=lambda row: row["date"])

        for row in sorted_matches:
            home_team = row["home_team"]
            away_team = row["away_team"]
            venue_country = row.get("venue_country", "")
            match_date = row["date"]
            prediction = self.predict_match(home_team, away_team, venue_country, match_date)
            if hasattr(match_date, "date"):
                match_date = match_date.date().isoformat()

            result = {
                "date": match_date,
                "stage": row.get("stage", ""),
                "venue": row.get("venue", ""),
                "venue_country": venue_country,
                "home_team": home_team,
                "away_team": away_team,
                **prediction,
                "home_score": row.get("home_score"),
                "away_score": row.get("away_score"),
                "actual_winner": self.get_actual_winner(
                    home_team,
                    away_team,
                    row.get("home_score"),
                    row.get("away_score"),
                ),
            }

            if row.get("home_score") is not None and row.get("away_score") is not None:
                self.update_elo(
                    home_team,
                    away_team,
                    int(row["home_score"]),
                    int(row["away_score"]),
                    venue_country,
                    row["date"],
                )

            result["home_post_elo"] = round(self.get_rating(home_team), 1)
            result["away_post_elo"] = round(self.get_rating(away_team), 1)
            predictions.append(result)

        return predictions

    def predict_knockout_matches(self, matches):
        predictions = []
        for row in sorted(matches, key=lambda item: item["match_number"]):
            team1 = row["team1"]
            team2 = row["team2"]
            venue_country = row.get("venue_country", "")
            prediction = self.predict_match(team1, team2, venue_country, row["date"])
            expected = self.expected_score(team1, team2, venue_country, row["date"])

            team1_advance_prob = (
                prediction["home_win_probability"]
                + prediction["draw_probability"] * expected
            )
            team2_advance_prob = (
                prediction["away_win_probability"]
                + prediction["draw_probability"] * (1 - expected)
            )
            advancing_team = team1 if team1_advance_prob >= team2_advance_prob else team2
            match_date = row["date"]
            if hasattr(match_date, "date"):
                match_date = match_date.date().isoformat()

            predictions.append({
                "round": row.get("round", ""),
                "match_number": row.get("match_number", ""),
                "date": match_date,
                "venue": row.get("venue", ""),
                "venue_country": venue_country,
                "team1": team1,
                "team2": team2,
                "team1_pre_elo": prediction["home_pre_elo"],
                "team2_pre_elo": prediction["away_pre_elo"],
                "team1_form_adjustment": prediction["home_form_adjustment"],
                "team2_form_adjustment": prediction["away_form_adjustment"],
                "team1_context_adjustment": prediction["home_context_adjustment"],
                "team2_context_adjustment": prediction["away_context_adjustment"],
                "team1_context_reason": prediction["home_context_reason"],
                "team2_context_reason": prediction["away_context_reason"],
                "team1_adjusted_elo": prediction["home_adjusted_elo"],
                "team2_adjusted_elo": prediction["away_adjusted_elo"],
                "home_advantage_team": prediction["home_advantage_team"],
                "team1_90min_win_probability": prediction["home_win_probability"],
                "draw_90min_probability": prediction["draw_probability"],
                "team2_90min_win_probability": prediction["away_win_probability"],
                "predicted_90min_result": prediction["predicted_result"],
                "team1_advance_probability": round(team1_advance_prob, 4),
                "team2_advance_probability": round(team2_advance_prob, 4),
                "predicted_advancing_team": advancing_team,
            })

        return predictions

    def predict_knockout_bracket(self, matches):
        predictions = []
        match_outcomes = {}

        for row in sorted(matches, key=lambda item: item["match_number"]):
            team1 = self.resolve_bracket_team(row.get("team1"), row.get("team1_source"), match_outcomes)
            team2 = self.resolve_bracket_team(row.get("team2"), row.get("team2_source"), match_outcomes)

            if not team1 or not team2:
                continue

            working_row = dict(row)
            working_row["team1"] = team1
            working_row["team2"] = team2
            prediction = self.predict_knockout_matches([working_row])[0]

            actual_advancing_team = row.get("actual_advancing_team", "")
            actual_runner_up = self.get_knockout_runner_up(team1, team2, actual_advancing_team)
            projected_advancing_team = actual_advancing_team or prediction["predicted_advancing_team"]
            projected_runner_up = self.get_knockout_runner_up(team1, team2, projected_advancing_team)

            prediction.update({
                "team1_source": row.get("team1_source", ""),
                "team2_source": row.get("team2_source", ""),
                "kickoff_utc": row.get("kickoff_utc", ""),
                "result_check_after_utc": row.get("result_check_after_utc", ""),
                "team1_score_90": row.get("team1_score_90"),
                "team2_score_90": row.get("team2_score_90"),
                "team1_score_final": row.get("team1_score_final"),
                "team2_score_final": row.get("team2_score_final"),
                "actual_advancing_team": actual_advancing_team,
                "projected_advancing_team": projected_advancing_team,
                "is_actual_result": bool(actual_advancing_team),
            })
            predictions.append(prediction)

            match_outcomes[row["match_number"]] = {
                "winner": projected_advancing_team,
                "runner_up": actual_runner_up or projected_runner_up,
            }

            if self.has_knockout_score(row):
                self.update_elo_from_knockout_result(row, team1, team2)

        return predictions

    def resolve_bracket_team(self, team, source, match_outcomes):
        if team:
            return team
        if not source:
            return ""

        parts = source.split()
        if len(parts) != 3:
            return ""

        outcome_type = parts[0]
        match_number = int(parts[2])
        outcome = match_outcomes.get(match_number, {})
        if outcome_type == "Winner":
            return outcome.get("winner", "")
        if outcome_type == "Runner-up":
            return outcome.get("runner_up", "")
        return ""

    def get_knockout_runner_up(self, team1, team2, advancing_team):
        if advancing_team == team1:
            return team2
        if advancing_team == team2:
            return team1
        return ""

    def has_knockout_score(self, row):
        return (
            row.get("team1_score_final") is not None
            and row.get("team2_score_final") is not None
        ) or (
            row.get("team1_score_90") is not None
            and row.get("team2_score_90") is not None
        )

    def update_elo_from_knockout_result(self, row, team1, team2):
        team1_score = row.get("team1_score_final")
        team2_score = row.get("team2_score_final")
        if team1_score is None or team2_score is None:
            team1_score = row.get("team1_score_90")
            team2_score = row.get("team2_score_90")

        if team1_score is None or team2_score is None:
            return

        self.update_elo(
            team1,
            team2,
            int(team1_score),
            int(team2_score),
            row.get("venue_country", ""),
            row.get("date"),
        )

    def process_historical_data(self):
        """Builds base ratings from your historical CSV."""
        if not os.path.exists(self.csv_path):
            print(f"Please place your historical data at {self.csv_path}")
            return

        with open(self.csv_path, newline="") as f:
            df = list(csv.DictReader(f))
        self.process_matches_chronologically(df)
        self.save_ratings()
        print("Historical data processed. Base ratings established.")

    def inject_daily_result(self, team1, team2, score1, score2):
        """Call this daily when a real-world match finishes."""
        self.update_elo(team1, team2, score1, score2)
        self.save_ratings()
        print(f"Updated ratings based on today's match: {team1} {score1} - {score2} {team2}")

    def save_ratings(self):
        with open(self.ratings_json, 'w') as f:
            json.dump(self.ratings, f, indent=4)

    def save_predictions(self, predictions_df, file_path="data/match_predictions.csv"):
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        if not predictions_df:
            return

        with open(file_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=predictions_df[0].keys())
            writer.writeheader()
            writer.writerows(predictions_df)

    def form_summary(self):
        rows = []
        for team in sorted(self.ratings):
            form_adjustment = self.form_adjustment(team)
            rows.append({
                "team": team,
                "current_elo": round(self.get_rating(team), 1),
                "form_score": round(self.form.get(team, 0.0), 4),
                "form_adjustment": round(form_adjustment, 1),
                "adjusted_neutral_elo": round(self.get_rating(team) + form_adjustment, 1),
            })

        return sorted(rows, key=lambda row: row["form_adjustment"], reverse=True)

    def save_form_summary(self, file_path="data/team_form_adjustments.csv"):
        rows = self.form_summary()
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        if not rows:
            return

        with open(file_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    def save_knockout_predictions(
        self,
        predictions,
        file_path="data/round_of_32_predictions.csv",
    ):
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        if not predictions:
            return

        with open(file_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=predictions[0].keys())
            writer.writeheader()
            writer.writerows(predictions)


if __name__ == "__main__":
    agent = DataAndRatingAgent()
    # Uncomment the line below to process your history file the first time:
    agent.process_historical_data()
