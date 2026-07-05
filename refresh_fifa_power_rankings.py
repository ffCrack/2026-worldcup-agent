import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


SOURCE_URL = "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/power-rankings"
FIELDNAMES = [
    "rank",
    "change",
    "player",
    "team",
    "attacking",
    "creativity",
    "defending",
    "goalkeeping_defending",
    "goalkeeping_possession",
    "overall_score",
    "source",
    "checked_at",
]


def read_round_of_16_teams(path):
    teams = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            if row.get("round") != "Round of 16":
                continue
            for field in ("team1", "team2"):
                team = row.get(field, "").strip()
                if team and team not in teams:
                    teams.append(team)
    return teams


def parse_number(value):
    value = (value or "").strip()
    if not value:
        return ""
    try:
        return f"{float(value):.2f}"
    except ValueError:
        return ""


def average_score(values):
    numbers = []
    for value in values:
        try:
            numbers.append(float(value))
        except (TypeError, ValueError):
            pass
    if not numbers:
        return ""
    return f"{sum(numbers) / len(numbers):.2f}"


def normalize_table_row(raw_row, source, checked_at):
    cells = raw_row.get("cells", [])
    if len(cells) < 4:
        return None

    rank_parts = [part.strip() for part in cells[0].splitlines() if part.strip()]
    player_parts = [part.strip() for part in cells[1].splitlines() if part.strip()]
    if not rank_parts or not player_parts:
        return None

    rank = rank_parts[0]
    change = rank_parts[1] if len(rank_parts) > 1 else ""
    player = player_parts[0]
    team = raw_row.get("selected_team", "")

    if raw_row.get("category") == "Outfield":
        attacking = parse_number(cells[2]) if len(cells) > 2 else ""
        creativity = parse_number(cells[3]) if len(cells) > 3 else ""
        defending = parse_number(cells[4]) if len(cells) > 4 else ""
        goalkeeping_defending = ""
        goalkeeping_possession = ""
        overall = average_score([attacking, creativity, defending])
    else:
        attacking = ""
        creativity = ""
        defending = ""
        goalkeeping_defending = parse_number(cells[2]) if len(cells) > 2 else ""
        goalkeeping_possession = parse_number(cells[3]) if len(cells) > 3 else ""
        overall = average_score([goalkeeping_defending, goalkeeping_possession])

    return {
        "rank": rank,
        "change": change,
        "player": player,
        "team": team,
        "attacking": attacking,
        "creativity": creativity,
        "defending": defending,
        "goalkeeping_defending": goalkeeping_defending,
        "goalkeeping_possession": goalkeeping_possession,
        "overall_score": overall,
        "source": source,
        "checked_at": checked_at,
    }


def normalize_rows(raw_rows, source, checked_at):
    rows = []
    seen = set()
    for raw_row in raw_rows:
        row = normalize_table_row(raw_row, source, checked_at)
        if not row:
            continue
        key = (row["team"], row["player"], row["rank"], bool(row["attacking"]))
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)

    def sort_key(row):
        try:
            rank = int(row["rank"])
        except ValueError:
            rank = 99999
        category = 0 if row["attacking"] else 1
        return (row["team"], category, rank, row["player"])

    return sorted(rows, key=sort_key)


def harvest_power_rankings(teams, headless=True, slow_mo=0):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is not installed. Install it with: python3 -m pip install playwright && python3 -m playwright install chromium"
        ) from exc

    raw_rows = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless, slow_mo=slow_mo)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(SOURCE_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(7000)

        current_filter = "All teams"
        for category in ("Outfield", "Goalkeeper"):
            page.get_by_role("button", name=category, exact=True).click(timeout=15000)
            page.wait_for_timeout(800)

            for team in teams:
                filter_button = page.get_by_role("button", name=current_filter, exact=True)
                if filter_button.count() != 1:
                    filter_button = page.get_by_role("button", name="All teams", exact=True)
                filter_button.click(timeout=15000)
                page.wait_for_timeout(300)
                page.get_by_role("option", name=team, exact=True).click(timeout=15000)
                current_filter = team
                page.wait_for_timeout(900)

                raw_rows.extend(
                    page.evaluate(
                        """({category, team}) => {
                            const table = document.querySelector("table");
                            if (!table) return [];
                            const headers = Array.from(table.querySelectorAll("thead th"))
                                .map((th) => th.innerText.trim());
                            return Array.from(table.querySelectorAll("tbody tr"))
                                .map((tr) => {
                                    const cells = Array.from(tr.querySelectorAll("td"))
                                        .map((td) => td.innerText.trim())
                                        .filter(Boolean);
                                    return { category, selected_team: team, headers, cells };
                                })
                                .filter((row) => row.cells.length >= 4);
                        }""",
                        {"category": category, "team": team},
                    )
                )

        browser.close()

    return raw_rows


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="Refresh FIFA Power Rankings for current Round of 16 teams.")
    parser.add_argument("--predictions", default="data/knockout_bracket_predictions.csv")
    parser.add_argument("--output", default="data/fifa_power_rankings.csv")
    parser.add_argument("--raw-output", default="data/fifa_power_rankings_harvest.json")
    parser.add_argument("--headed", action="store_true", help="Show the browser while harvesting.")
    parser.add_argument("--slow-mo", type=int, default=0, help="Slow browser actions by this many milliseconds.")
    args = parser.parse_args()

    teams = read_round_of_16_teams(args.predictions)
    if not teams:
        raise SystemExit("No Round of 16 teams found. Run main.py first.")

    checked_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    try:
        raw_rows = harvest_power_rankings(teams, headless=not args.headed, slow_mo=args.slow_mo)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from None
    rows = normalize_rows(raw_rows, SOURCE_URL, checked_at)

    write_csv(Path(args.output), rows)
    Path(args.raw_output).write_text(
        json.dumps(
            {
                "source": SOURCE_URL,
                "checked_at": checked_at,
                "teams": teams,
                "raw_row_count": len(raw_rows),
                "normalized_row_count": len(rows),
                "rows": raw_rows,
            },
            indent=2,
        )
    )
    print(f"Wrote {len(rows)} FIFA Power Ranking rows for {len(teams)} teams.")


if __name__ == "__main__":
    main()
