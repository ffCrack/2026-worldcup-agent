import json
import random


class MatchSimulationAgent:
    def __init__(self, ratings_json="data/team_ratings.json"):
        with open(ratings_json, "r") as f:
            self.ratings = json.load(f)

    def get_rating(self, team):
        return self.ratings.get(team, 1500.0)

    def simulate_single_match(self, team1, team2, allow_draw=False):
        """Simulates a match based on the Elo difference."""
        r1 = self.get_rating(team1)
        r2 = self.get_rating(team2)

        # Win probability for team 1
        prob1 = 1 / (1 + 10 ** ((r2 - r1) / 400))

        rand = random.random()

        if allow_draw:
            # Simple threshold for a draw in group stages
            if 0.45 <= rand <= 0.55:
                return "Draw"
            elif rand < 0.45:
                return team1 if prob1 > 0.5 else team2
            else:
                return team2 if prob1 > 0.5 else team1
        else:
            # Knockout stage (must have a winner)
            return team1 if rand < prob1 else team2

    def simulate_bracket(self, remaining_teams):
        """Pass a list of teams left in the tournament (Must be 2, 4, or 8 teams)."""
        current_round = remaining_teams

        while len(current_round) > 1:
            next_round = []
            # Step by 2 to pair teams up: (0 vs 1), (2 vs 3), etc.
            for i in range(0, len(current_round), 2):
                winner = self.simulate_single_match(current_round[i], current_round[i + 1], allow_draw=False)
                next_round.append(winner)
            current_round = next_round

        return current_round[0]  # Return the Champion

    def run_monte_carlo(self, teams_list, iterations=1000):
        """Runs the tournament bracket thousands of times to find the favorite."""
        results = {}
        for team in teams_list:
            results[team] = 0

        print(f"Running {iterations} tournament simulations...")
        for _ in range(iterations):
            winner = self.simulate_bracket(teams_list)
            results[winner] += 1

        print("\n--- PROBABILITY TO WIN WORLD CUP ---")
        sorted_results = sorted(results.items(), key=lambda x: x[1], reverse=True)
        for team, wins in sorted_results:
            pct = (wins / iterations) * 100
            if pct > 0:
                print(f"{team}: {pct:.1f}% chance")


if __name__ == "__main__":
    sim = MatchSimulationAgent()
    # Example: Replace this list with whatever teams are currently in the knockout stage
    current_bracket = ["Argentina", "France", "Brazil", "England", "Spain", "Germany", "Portugal", "Morocco"]
    sim.run_monte_carlo(current_bracket, iterations=5000)
