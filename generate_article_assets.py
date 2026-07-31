import csv
import html
import os


ASSET_DIR = "docs/assets"


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def pct(value):
    return float(value) * 100


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


def bar_chart(title, rows, value_key, label_key, output_path, color="#176b87"):
    width = 1100
    row_height = 42
    top = 84
    left = 260
    right = 80
    height = top + len(rows) * row_height + 48
    max_value = max(abs(float(row[value_key])) for row in rows) or 1
    chart_width = width - left - right

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f7f8fa"/>',
        f'<text x="40" y="46" font-family="Arial, sans-serif" font-size="28" font-weight="700" fill="#20242b">{html.escape(title)}</text>',
        '<text x="40" y="72" font-family="Arial, sans-serif" font-size="14" fill="#667085">Generated from the model output CSVs</text>',
    ]

    for index, row in enumerate(rows):
        y = top + index * row_height
        label = row[label_key]
        value = float(row[value_key])
        bar_width = abs(value) / max_value * chart_width
        x = left
        parts.extend([
            f'<text x="40" y="{y + 24}" font-family="Arial, sans-serif" font-size="17" fill="#20242b">{html.escape(label)}</text>',
            f'<rect x="{x}" y="{y + 6}" width="{bar_width:.1f}" height="24" rx="5" fill="{color}"/>',
            f'<text x="{x + bar_width + 10}" y="{y + 24}" font-family="Arial, sans-serif" font-size="16" font-weight="700" fill="#20242b">{value:.1f}</text>',
        ])

    parts.append("</svg>")
    write(output_path, "\n".join(parts))


def grouped_probability_chart(rows, output_path):
    width = 1200
    row_height = 52
    top = 92
    left = 300
    chart_width = 600
    height = top + len(rows) * row_height + 52
    colors = {
        "team1": "#176b87",
        "draw": "#b44b38",
        "team2": "#217a4d",
    }

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f7f8fa"/>',
        '<text x="40" y="46" font-family="Arial, sans-serif" font-size="28" font-weight="700" fill="#20242b">Round of 32: 90-Minute Probabilities</text>',
        '<text x="40" y="72" font-family="Arial, sans-serif" font-size="14" fill="#667085">Blue = team 1 win, red = draw, green = team 2 win</text>',
    ]

    for index, row in enumerate(rows):
        y = top + index * row_height
        team_label = f"{row['team1']} vs {row['team2']}"
        p1 = pct(row["team1_90min_win_probability"])
        pd = pct(row["draw_90min_probability"])
        p2 = pct(row["team2_90min_win_probability"])
        w1 = p1 / 100 * chart_width
        wd = pd / 100 * chart_width
        w2 = p2 / 100 * chart_width

        parts.extend([
            f'<text x="40" y="{y + 24}" font-family="Arial, sans-serif" font-size="16" fill="#20242b">{html.escape(team_label)}</text>',
            f'<rect x="{left}" y="{y + 8}" width="{w1:.1f}" height="22" fill="{colors["team1"]}"/>',
            f'<rect x="{left + w1:.1f}" y="{y + 8}" width="{wd:.1f}" height="22" fill="{colors["draw"]}"/>',
            f'<rect x="{left + w1 + wd:.1f}" y="{y + 8}" width="{w2:.1f}" height="22" fill="{colors["team2"]}"/>',
            f'<text x="{left + chart_width + 18}" y="{y + 24}" font-family="Arial, sans-serif" font-size="15" fill="#20242b">{p1:.0f}% / {pd:.0f}% / {p2:.0f}%</text>',
        ])

    parts.append("</svg>")
    write(output_path, "\n".join(parts))


def champion_path_chart(rows, output_path):
    width = 1100
    height = 620
    final = next(row for row in rows if row["round"] == "Final")
    semis = [row for row in rows if row["round"] == "Semi-final"]
    quarters = [row for row in rows if row["round"] == "Quarter-final"]
    champion = final["projected_advancing_team"]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f7f8fa"/>',
        '<text x="40" y="48" font-family="Arial, sans-serif" font-size="30" font-weight="700" fill="#20242b">Projected Knockout Path</text>',
        '<text x="40" y="76" font-family="Arial, sans-serif" font-size="15" fill="#667085">Current model projection from quarter-finals to champion</text>',
    ]

    def box(x, y, row, label):
        winner = row["projected_advancing_team"]
        text = f"{label} #{row['match_number']}: {row['team1']} vs {row['team2']}"
        parts.extend([
            f'<rect x="{x}" y="{y}" width="300" height="86" rx="8" fill="#ffffff" stroke="#d8dee8"/>',
            f'<text x="{x + 16}" y="{y + 28}" font-family="Arial, sans-serif" font-size="14" fill="#667085">{html.escape(text)}</text>',
            f'<text x="{x + 16}" y="{y + 58}" font-family="Arial, sans-serif" font-size="22" font-weight="700" fill="#176b87">{html.escape(winner)}</text>',
        ])

    for i, row in enumerate(quarters):
        box(40, 116 + i * 112, row, "QF")
    for i, row in enumerate(semis):
        box(420, 172 + i * 224, row, "SF")
    box(780, 284, final, "Final")
    parts.extend([
        '<rect x="780" y="420" width="300" height="100" rx="8" fill="#176b87"/>',
        '<text x="800" y="456" font-family="Arial, sans-serif" font-size="16" fill="#e6f2f5">Projected Champion</text>',
        f'<text x="800" y="494" font-family="Arial, sans-serif" font-size="34" font-weight="800" fill="#ffffff">{html.escape(champion)}</text>',
    ])
    parts.append("</svg>")
    write(output_path, "\n".join(parts))


def later_rounds_overview_chart(rows, output_path):
    rounds = ["Round of 16", "Quarter-final", "Semi-final", "Final"]
    grouped = {
        round_name: [row for row in rows if row["round"] == round_name]
        for round_name in rounds
    }
    width = 1500
    height = 980
    column_width = 345
    left = 36
    top = 132
    gap = 20

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f7f8fa"/>',
        '<text x="40" y="48" font-family="Arial, sans-serif" font-size="30" font-weight="700" fill="#20242b">Projected Knockout Rounds</text>',
        '<text x="40" y="78" font-family="Arial, sans-serif" font-size="15" fill="#667085">Round of 16 through the final, based on the current model projection</text>',
    ]

    for round_index, round_name in enumerate(rounds):
        x = left + round_index * (column_width + gap)
        parts.extend([
            f'<text x="{x}" y="{top - 22}" font-family="Arial, sans-serif" font-size="22" font-weight="700" fill="#176b87">{html.escape(round_name)}</text>',
            f'<rect x="{x}" y="{top - 8}" width="{column_width}" height="{height - top - 32}" rx="8" fill="#ffffff" stroke="#d8dee8"/>',
        ])
        y = top + 18
        card_height = 78 if round_name == "Round of 16" else 92
        for row in grouped[round_name]:
            winner = row["projected_advancing_team"]
            p1 = pct(row["team1_advance_probability"])
            p2 = pct(row["team2_advance_probability"])
            subtitle = f"#{row['match_number']}  {row['date']}"
            matchup = f"{row['team1']} vs {row['team2']}"
            odds = f"{p1:.0f}% / {p2:.0f}%"
            parts.extend([
                f'<rect x="{x + 14}" y="{y}" width="{column_width - 28}" height="{card_height - 10}" rx="7" fill="#fbfcfd" stroke="#e6eaf0"/>',
                f'<text x="{x + 28}" y="{y + 24}" font-family="Arial, sans-serif" font-size="13" fill="#667085">{html.escape(subtitle)}</text>',
                f'<text x="{x + 28}" y="{y + 45}" font-family="Arial, sans-serif" font-size="15" font-weight="700" fill="#20242b">{html.escape(matchup)}</text>',
                f'<text x="{x + 28}" y="{y + 66}" font-family="Arial, sans-serif" font-size="14" fill="#667085">Advance: {html.escape(odds)}</text>',
                f'<text x="{x + column_width - 32}" y="{y + 66}" text-anchor="end" font-family="Arial, sans-serif" font-size="16" font-weight="800" fill="#9a5b00">{html.escape(winner)}</text>',
            ])
            y += card_height

    parts.append("</svg>")
    write(output_path, "\n".join(parts))


def prediction_record_chart(evaluation_rows, output_path):
    total = len(evaluation_rows)
    hits = sum(1 for row in evaluation_rows if row["evaluation"] == "Hit")
    misses = total - hits
    hit_rate = hits / total * 100 if total else 0
    width = 1100
    height = 520
    hit_width = 760 * hits / total if total else 0
    miss_width = 760 * misses / total if total else 0

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f7f8fa"/>',
        '<text x="52" y="62" font-family="Arial, sans-serif" font-size="32" font-weight="800" fill="#20242b">Knockout Prediction Record</text>',
        '<text x="52" y="94" font-family="Arial, sans-serif" font-size="16" fill="#667085">Completed matches only, using pre-result prediction locks</text>',
        '<rect x="52" y="136" width="300" height="150" rx="8" fill="#ffffff" stroke="#d8dee8"/>',
        '<text x="78" y="182" font-family="Arial, sans-serif" font-size="18" fill="#667085">Hits</text>',
        f'<text x="78" y="248" font-family="Arial, sans-serif" font-size="62" font-weight="800" fill="#176b87">{hits}</text>',
        '<rect x="394" y="136" width="300" height="150" rx="8" fill="#ffffff" stroke="#d8dee8"/>',
        '<text x="420" y="182" font-family="Arial, sans-serif" font-size="18" fill="#667085">Misses</text>',
        f'<text x="420" y="248" font-family="Arial, sans-serif" font-size="62" font-weight="800" fill="#b44b38">{misses}</text>',
        '<rect x="736" y="136" width="300" height="150" rx="8" fill="#ffffff" stroke="#d8dee8"/>',
        '<text x="762" y="182" font-family="Arial, sans-serif" font-size="18" fill="#667085">Hit Rate</text>',
        f'<text x="762" y="248" font-family="Arial, sans-serif" font-size="62" font-weight="800" fill="#217a4d">{hit_rate:.1f}%</text>',
        '<text x="52" y="346" font-family="Arial, sans-serif" font-size="20" font-weight="700" fill="#20242b">Final scorecard</text>',
        '<rect x="52" y="376" width="760" height="32" rx="8" fill="#e6eaf0"/>',
        f'<rect x="52" y="376" width="{hit_width:.1f}" height="32" rx="8" fill="#176b87"/>',
        f'<rect x="{52 + hit_width:.1f}" y="376" width="{miss_width:.1f}" height="32" rx="8" fill="#b44b38"/>',
        f'<text x="52" y="442" font-family="Arial, sans-serif" font-size="16" fill="#667085">Hit {hits}/{total}. The misses became training signals for the next version of the workflow.</text>',
    ]
    parts.append("</svg>")
    write(output_path, "\n".join(parts))


def misses_summary_chart(evaluation_rows, output_path):
    misses = [row for row in evaluation_rows if row["evaluation"] == "Miss"]
    width = 1300
    row_height = 86
    top = 136
    height = top + len(misses) * row_height + 58

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f7f8fa"/>',
        '<text x="44" y="56" font-family="Arial, sans-serif" font-size="32" font-weight="800" fill="#20242b">The Misses That Changed the Model</text>',
        '<text x="44" y="88" font-family="Arial, sans-serif" font-size="16" fill="#667085">Each miss is shown with the model pick, actual winner, and the actual winner pre-match advance probability.</text>',
        '<rect x="44" y="112" width="1212" height="40" rx="6" fill="#20242b"/>',
        '<text x="64" y="138" font-family="Arial, sans-serif" font-size="14" font-weight="700" fill="#ffffff">Match</text>',
        '<text x="410" y="138" font-family="Arial, sans-serif" font-size="14" font-weight="700" fill="#ffffff">Model Pick</text>',
        '<text x="650" y="138" font-family="Arial, sans-serif" font-size="14" font-weight="700" fill="#ffffff">Actual Winner</text>',
        '<text x="920" y="138" font-family="Arial, sans-serif" font-size="14" font-weight="700" fill="#ffffff">Actual Winner Probability</text>',
    ]

    for index, row in enumerate(misses):
        y = top + index * row_height
        matchup = f"#{row['match_number']} {row['team1']} vs {row['team2']}"
        prob = pct(row["actual_advance_probability"])
        parts.extend([
            f'<rect x="44" y="{y}" width="1212" height="70" rx="8" fill="#ffffff" stroke="#d8dee8"/>',
            f'<text x="64" y="{y + 28}" font-family="Arial, sans-serif" font-size="17" font-weight="700" fill="#20242b">{html.escape(matchup)}</text>',
            f'<text x="64" y="{y + 52}" font-family="Arial, sans-serif" font-size="14" fill="#667085">{html.escape(row["round"])} · actual {html.escape(row["actual_score"])}</text>',
            f'<text x="410" y="{y + 42}" font-family="Arial, sans-serif" font-size="18" fill="#b44b38">{html.escape(row["predicted_advancing_team"])}</text>',
            f'<text x="650" y="{y + 42}" font-family="Arial, sans-serif" font-size="18" font-weight="800" fill="#176b87">{html.escape(row["actual_advancing_team"])}</text>',
            f'<text x="920" y="{y + 42}" font-family="Arial, sans-serif" font-size="18" font-weight="800" fill="#20242b">{prob:.1f}%</text>',
        ])

    parts.append("</svg>")
    write(output_path, "\n".join(parts))


def final_prediction_chart(evaluation_rows, output_path):
    final = next(row for row in evaluation_rows if row["round"] == "Final")
    winner = final["predicted_advancing_team"]
    actual = final["actual_advancing_team"]
    probability = pct(final["actual_advance_probability"])
    other_probability = 100 - probability
    width = 1100
    height = 560
    bar_width = 860
    winner_width = bar_width * probability / 100

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f7f8fa"/>',
        '<text x="54" y="62" font-family="Arial, sans-serif" font-size="32" font-weight="800" fill="#20242b">Final Prediction: Spain vs Argentina</text>',
        '<text x="54" y="94" font-family="Arial, sans-serif" font-size="16" fill="#667085">The locked pre-match model gave Spain a narrow edge. The final result confirmed it.</text>',
        '<rect x="54" y="136" width="992" height="270" rx="8" fill="#ffffff" stroke="#d8dee8"/>',
        f'<text x="86" y="196" font-family="Arial, sans-serif" font-size="24" font-weight="800" fill="#176b87">{html.escape(winner)}</text>',
        f'<text x="86" y="236" font-family="Arial, sans-serif" font-size="52" font-weight="800" fill="#176b87">{probability:.1f}%</text>',
        '<text x="86" y="270" font-family="Arial, sans-serif" font-size="16" fill="#667085">advance probability before kickoff</text>',
        '<text x="520" y="196" font-family="Arial, sans-serif" font-size="24" font-weight="800" fill="#20242b">Actual Result</text>',
        f'<text x="520" y="244" font-family="Arial, sans-serif" font-size="42" font-weight="800" fill="#217a4d">{html.escape(actual)} {html.escape(final["actual_score"])}</text>',
        '<text x="520" y="278" font-family="Arial, sans-serif" font-size="16" fill="#667085">Spain won after extra time</text>',
        '<rect x="86" y="332" width="860" height="30" rx="8" fill="#dfe6ee"/>',
        f'<rect x="86" y="332" width="{winner_width:.1f}" height="30" rx="8" fill="#176b87"/>',
        f'<text x="86" y="390" font-family="Arial, sans-serif" font-size="15" fill="#667085">Spain {probability:.1f}% · Argentina {other_probability:.1f}%</text>',
        '<rect x="54" y="438" width="992" height="66" rx="8" fill="#edf7f1" stroke="#c9e8d4"/>',
        '<text x="86" y="480" font-family="Arial, sans-serif" font-size="20" font-weight="800" fill="#217a4d">Final evaluation: Hit</text>',
    ]
    parts.append("</svg>")
    write(output_path, "\n".join(parts))


def workflow_chart(output_path):
    width = 1400
    height = 520
    boxes = [
        ("Match finishes", "Score, ET, penalties, cards"),
        ("Harvest result", "Write structured CSV rows"),
        ("Lock prediction", "Keep the pre-result forecast"),
        ("Evaluate", "Hit, miss, surprise score"),
        ("Adjust signals", "Form, network, stars, news"),
        ("Repredict bracket", "Dashboard refreshes"),
    ]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f7f8fa"/>',
        '<text x="48" y="58" font-family="Arial, sans-serif" font-size="32" font-weight="800" fill="#20242b">The Iteration Loop</text>',
        '<text x="48" y="90" font-family="Arial, sans-serif" font-size="16" fill="#667085">The project became less about one perfect model and more about a transparent update workflow.</text>',
    ]
    for index, (title, subtitle) in enumerate(boxes):
        x = 48 + index * 220
        y = 178
        fill = "#ffffff" if index % 2 == 0 else "#fbfcfd"
        parts.extend([
            f'<rect x="{x}" y="{y}" width="176" height="128" rx="8" fill="{fill}" stroke="#d8dee8"/>',
            f'<text x="{x + 18}" y="{y + 44}" font-family="Arial, sans-serif" font-size="18" font-weight="800" fill="#20242b">{html.escape(title)}</text>',
            f'<text x="{x + 18}" y="{y + 78}" font-family="Arial, sans-serif" font-size="14" fill="#667085">{html.escape(subtitle)}</text>',
        ])
        if index < len(boxes) - 1:
            arrow_x = x + 184
            parts.extend([
                f'<line x1="{arrow_x}" y1="{y + 64}" x2="{arrow_x + 42}" y2="{y + 64}" stroke="#176b87" stroke-width="3"/>',
                f'<path d="M {arrow_x + 42} {y + 64} L {arrow_x + 30} {y + 56} L {arrow_x + 30} {y + 72} Z" fill="#176b87"/>',
            ])
    parts.extend([
        '<rect x="48" y="374" width="1268" height="76" rx="8" fill="#ffffff" stroke="#d8dee8"/>',
        '<text x="78" y="418" font-family="Arial, sans-serif" font-size="19" font-weight="800" fill="#20242b">Design principle</text>',
        '<text x="250" y="418" font-family="Arial, sans-serif" font-size="17" fill="#667085">Every update should be traceable: what changed, why it changed, and whether the previous prediction was right.</text>',
    ])
    parts.append("</svg>")
    write(output_path, "\n".join(parts))


def main():
    form_rows = read_csv("data/team_form_adjustments.csv")[:12]
    knockout_rows = read_csv("data/knockout_bracket_predictions.csv")
    evaluation_rows = read_csv("data/prediction_evaluation.csv")
    round_32 = [row for row in knockout_rows if row["round"] == "Round of 32"][:8]

    bar_chart(
        "Top Tournament Form Adjustments",
        form_rows,
        "form_adjustment",
        "team",
        os.path.join(ASSET_DIR, "top_form_adjustments.svg"),
    )
    grouped_probability_chart(
        round_32,
        os.path.join(ASSET_DIR, "round_of_32_probabilities.svg"),
    )
    champion_path_chart(
        knockout_rows,
        os.path.join(ASSET_DIR, "projected_knockout_path.svg"),
    )
    later_rounds_overview_chart(
        knockout_rows,
        os.path.join(ASSET_DIR, "later_rounds_overview.svg"),
    )
    prediction_record_chart(
        evaluation_rows,
        os.path.join(ASSET_DIR, "prediction_record.svg"),
    )
    misses_summary_chart(
        evaluation_rows,
        os.path.join(ASSET_DIR, "misses_summary.svg"),
    )
    final_prediction_chart(
        evaluation_rows,
        os.path.join(ASSET_DIR, "final_prediction_summary.svg"),
    )
    workflow_chart(
        os.path.join(ASSET_DIR, "model_iteration_workflow.svg"),
    )
    print(f"[Article Assets]: Wrote SVG charts to {ASSET_DIR}")


if __name__ == "__main__":
    main()
