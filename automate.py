from main import main as run_model
from generate_dashboard import main as generate_dashboard
from src.automation_agent import AutomatedUpdateAgent
from src.run_history import RunHistoryRecorder
from validate_match_results import validate_knockout_results
from evaluate_predictions import evaluate_predictions


def main():
    print("=== STARTING AUTOMATED WORLD CUP UPDATE ===")
    automation_agent = AutomatedUpdateAgent()
    summary = automation_agent.run()
    print(
        "[Automation]: "
        f"{summary['power_ranking_updates']} power-ranking refreshes applied; "
        f"{summary['player_score_updates']} player-score rows updated; "
        f"{summary['news_results_harvested']} news result rows harvested; "
        f"{summary['match_result_updates']} match-result fields updated; "
        f"{summary['strength_adjustments_applied']} strength adjustments applied; "
        f"{summary['news_adjustments_applied']} news/context adjustments applied."
    )

    print("\n[Automation]: Re-running prediction model with updated inputs...")
    run_model()
    evaluation_rows = evaluate_predictions()
    misses = sum(1 for row in evaluation_rows if row["evaluation"] == "Miss")
    print(f"[Evaluation]: {len(evaluation_rows)} completed knockout predictions evaluated; {misses} misses.")
    generate_dashboard()
    manifest = RunHistoryRecorder().record_if_needed("automated_update", summary)
    if manifest:
        print(f"[History]: Snapshot saved to data/run_history/{manifest['run_id']}")
    else:
        print("[History]: No snapshot needed; no model inputs changed and today's checkpoint already exists.")

    issues = validate_knockout_results()
    if issues:
        print("[Validation]: Missing knockout scores found:")
        for issue in issues:
            print(
                f"- Match {issue['match_number']} ({issue['date']}): "
                f"{issue['teams']} - {issue['issue']}"
            )
    else:
        print("[Validation]: All completed/past knockout matches have scores.")


if __name__ == "__main__":
    main()
