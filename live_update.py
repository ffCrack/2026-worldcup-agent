import argparse
import time
from datetime import datetime

from automate import main as run_automated_update


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run the World Cup automation pipeline on a timed loop."
    )
    parser.add_argument(
        "--interval-minutes",
        type=float,
        default=15,
        help="Minutes to wait between update checks. Default: 15.",
    )
    parser.add_argument(
        "--max-runs",
        type=int,
        default=0,
        help="Optional number of runs before stopping. Default: 0 means unlimited.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    interval_seconds = max(args.interval_minutes, 1) * 60
    run_number = 0

    print("=== STARTING LIVE WORLD CUP UPDATE LOOP ===")
    print(f"[Live Update]: Checking every {args.interval_minutes} minutes.")
    if args.max_runs:
        print(f"[Live Update]: Stopping after {args.max_runs} runs.")

    while True:
        run_number += 1
        print(f"\n[Live Update]: Run {run_number} started at {datetime.now().isoformat(timespec='seconds')}")
        try:
            run_automated_update()
        except Exception as exc:
            print(f"[Live Update]: Update failed: {exc}")

        if args.max_runs and run_number >= args.max_runs:
            print("[Live Update]: Max runs reached. Stopping.")
            break

        print(f"[Live Update]: Sleeping for {args.interval_minutes} minutes...")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    main()
