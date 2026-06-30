import csv
from datetime import date, datetime


KNOCKOUT_BRACKET_CSV = "data/knockout_bracket.csv"


def parse_date(value):
    return datetime.fromisoformat(value).date()


def has_score(row):
    has_90 = row.get("team1_score_90") != "" and row.get("team2_score_90") != ""
    has_final = row.get("team1_score_final") != "" and row.get("team2_score_final") != ""
    return has_90 or has_final


def validate_knockout_results(file_path=KNOCKOUT_BRACKET_CSV, today=None):
    today = today or date.today()
    issues = []

    with open(file_path, newline="") as f:
        rows = list(csv.DictReader(f))

    for row in rows:
        match_date = parse_date(row["date"])
        actual_advancing_team = row.get("actual_advancing_team", "")

        if actual_advancing_team and not has_score(row):
            issues.append({
                "match_number": row["match_number"],
                "date": row["date"],
                "teams": f"{row.get('team1') or row.get('team1_source')} vs {row.get('team2') or row.get('team2_source')}",
                "issue": "actual advancing team is recorded, but score is missing",
            })
        elif match_date < today and not has_score(row):
            issues.append({
                "match_number": row["match_number"],
                "date": row["date"],
                "teams": f"{row.get('team1') or row.get('team1_source')} vs {row.get('team2') or row.get('team2_source')}",
                "issue": "match date is in the past, but score is missing",
            })

    return issues


def main():
    issues = validate_knockout_results()
    if not issues:
        print("[Validation]: All completed/past knockout matches have scores.")
        return

    print("[Validation]: Missing knockout scores found:")
    for issue in issues:
        print(
            f"- Match {issue['match_number']} ({issue['date']}): "
            f"{issue['teams']} - {issue['issue']}"
        )


if __name__ == "__main__":
    main()
