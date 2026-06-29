from main import main as run_model
from generate_dashboard import main as generate_dashboard
from src.automation_agent import AutomatedUpdateAgent
from src.run_history import RunHistoryRecorder


def main():
    print("=== STARTING AUTOMATED WORLD CUP UPDATE ===")
    automation_agent = AutomatedUpdateAgent()
    summary = automation_agent.run()
    print(
        "[Automation]: "
        f"{summary['match_result_updates']} match-result fields updated; "
        f"{summary['news_adjustments_applied']} news/context adjustments applied."
    )

    print("\n[Automation]: Re-running prediction model with updated inputs...")
    run_model()
    generate_dashboard()
    manifest = RunHistoryRecorder().record_if_needed("automated_update", summary)
    if manifest:
        print(f"[History]: Snapshot saved to data/run_history/{manifest['run_id']}")
    else:
        print("[History]: No snapshot needed; no model inputs changed and today's checkpoint already exists.")


if __name__ == "__main__":
    main()
