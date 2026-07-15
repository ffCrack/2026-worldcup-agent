import csv
import html
import json
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


OUTPUT_PATH = "data/dashboard.html"
DISPLAY_TIME_ZONE = "America/Los_Angeles"


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def pct(value):
    if value in (None, ""):
        return ""
    return f"{float(value) * 100:.1f}%"


def western_timestamp(value=None):
    if value is None:
        value = datetime.now(timezone.utc)
    return value.astimezone(ZoneInfo(DISPLAY_TIME_ZONE)).strftime("%Y-%m-%d %I:%M %p %Z")


def build_dashboard_data():
    knockout = read_csv("data/knockout_bracket_predictions.csv")
    group = read_csv("data/match_predictions.csv")
    history = read_csv("data/run_history/index.csv")
    evaluation = read_csv("data/prediction_evaluation.csv")
    player_strength = read_csv("data/team_player_strength.csv")
    intelligence = read_csv("data/match_intelligence_notes.csv")
    high_stakes = read_csv("data/high_stakes_predictions.csv")

    final = next((row for row in knockout if row.get("round") == "Final"), {})
    completed_knockouts = [
        row for row in knockout
        if row.get("is_actual_result") == "True"
    ]
    misses = [
        row for row in evaluation
        if row.get("evaluation") == "Miss"
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generated_at_display": western_timestamp(),
        "projected_champion": final.get("projected_advancing_team", ""),
        "final": final,
        "knockout": knockout,
        "group": group,
        "history": history,
        "evaluation": evaluation,
        "player_strength": player_strength,
        "intelligence": intelligence,
        "high_stakes": high_stakes,
        "completed_knockout_count": len(completed_knockouts),
        "prediction_hit_count": len(evaluation) - len(misses),
        "prediction_miss_count": len(misses),
    }


def json_script(data):
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def render_html(data):
    champion = html.escape(data.get("projected_champion") or "TBD")
    generated_at = html.escape(data.get("generated_at_display") or data["generated_at"])
    payload = json_script(data)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>World Cup Prediction Dashboard</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f8fa;
      --panel: #ffffff;
      --text: #20242b;
      --muted: #667085;
      --line: #d9dee7;
      --accent: #176b87;
      --accent-2: #b44b38;
      --ok: #217a4d;
      --warn: #9a5b00;
      --shadow: 0 1px 2px rgba(16, 24, 40, 0.06);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
    }}
    header {{
      background: #ffffff;
      border-bottom: 1px solid var(--line);
      padding: 20px 24px 16px;
    }}
    .topbar {{
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 16px;
      max-width: 1440px;
      margin: 0 auto;
    }}
    h1 {{
      margin: 0;
      font-size: 24px;
      font-weight: 760;
      letter-spacing: 0;
    }}
    .subtle {{ color: var(--muted); font-size: 13px; }}
    main {{
      max-width: 1440px;
      margin: 0 auto;
      padding: 18px 24px 28px;
    }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(4, minmax(160px, 1fr));
      gap: 12px;
      margin-bottom: 16px;
    }}
    .metric {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      box-shadow: var(--shadow);
      min-height: 88px;
    }}
    .metric-label {{
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 8px;
    }}
    .metric-value {{
      font-size: 22px;
      font-weight: 760;
      overflow-wrap: anywhere;
    }}
    .toolbar {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 10px;
      margin: 14px 0;
    }}
    .tabs, .rounds {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }}
    button, select, input {{
      border: 1px solid var(--line);
      background: #fff;
      color: var(--text);
      border-radius: 6px;
      min-height: 36px;
      padding: 0 10px;
      font: inherit;
      font-size: 14px;
    }}
    button {{
      cursor: pointer;
      font-weight: 650;
    }}
    button.active {{
      background: var(--accent);
      color: #fff;
      border-color: var(--accent);
    }}
    input {{
      width: min(360px, 100%);
    }}
    .table-wrap {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      overflow: auto;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 1120px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 10px 12px;
      text-align: left;
      vertical-align: top;
      font-size: 13px;
      white-space: nowrap;
    }}
    th {{
      position: sticky;
      top: 0;
      background: #eef3f6;
      color: #344054;
      z-index: 1;
    }}
    tr.actual td {{ background: #f0f8f4; }}
    tr.miss td {{ background: #fff1f0; }}
    .team {{
      font-weight: 720;
      color: var(--text);
    }}
    .muted {{ color: var(--muted); }}
    .pill {{
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      padding: 2px 8px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: #fff;
      font-size: 12px;
      font-weight: 700;
    }}
    .pill.actual {{ color: var(--ok); border-color: #b7dfc9; background: #edf8f2; }}
    .pill.projected {{ color: var(--warn); border-color: #ead2a8; background: #fff8ea; }}
    .pill.miss {{ color: var(--accent-2); border-color: #f3b8b1; background: #fff1f0; }}
    .pill.live {{ color: #134e63; border-color: #8fc5d2; background: #e6f2f5; }}
    .pill.due {{ color: var(--accent-2); border-color: #f3b8b1; background: #fff1f0; }}
    .pill.today {{ color: var(--warn); border-color: #ead2a8; background: #fff8ea; }}
    .reason {{
      max-width: 360px;
      white-space: normal;
      color: var(--muted);
    }}
    @media (max-width: 900px) {{
      header {{ padding: 16px; }}
      main {{ padding: 14px 16px 22px; }}
      .topbar {{ align-items: flex-start; flex-direction: column; }}
      .summary {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .metric-value {{ font-size: 19px; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="topbar">
      <div>
        <h1>World Cup Prediction Dashboard</h1>
        <div class="subtle">Generated at {generated_at}</div>
      </div>
      <div class="subtle">Projected champion: <strong>{champion}</strong></div>
    </div>
  </header>

  <main>
    <section class="summary" id="summary"></section>

    <div class="toolbar">
      <div class="tabs">
        <button id="tab-knockout" class="active" type="button">Knockout</button>
        <button id="tab-evaluation" type="button">Evaluation</button>
        <button id="tab-high-stakes" type="button">High Stakes</button>
        <button id="tab-intelligence" type="button">Intelligence</button>
        <button id="tab-group" type="button">Group History</button>
        <button id="tab-runs" type="button">Run History</button>
      </div>
      <input id="match-date" type="date" aria-label="Match date">
      <button id="clear-date" type="button">All Dates</button>
      <input id="search" type="search" placeholder="Search team, venue, round">
      <div class="rounds" id="rounds"></div>
    </div>

    <section class="table-wrap">
      <table>
        <thead id="thead"></thead>
        <tbody id="tbody"></tbody>
      </table>
    </section>
  </main>

  <script>
    const DATA = {payload};
    const DISPLAY_TIME_ZONE = "America/Los_Angeles";
    let currentTab = "knockout";
    let currentRound = "All";

    const rounds = ["All", ...new Set(DATA.knockout.map(row => row.round).filter(Boolean))];

    function fmtPct(value) {{
      if (value === undefined || value === null || value === "") return "";
      return `${{(Number(value) * 100).toFixed(1)}}%`;
    }}

    function score(row) {{
      const s1 = row.team1_score_final || row.team1_score_90;
      const s2 = row.team2_score_final || row.team2_score_90;
      if (s1 === "" || s2 === "" || s1 === undefined || s2 === undefined) return "";
      return `${{s1}}-${{s2}}`;
    }}

    function dateKey(date) {{
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, "0");
      const day = String(date.getDate()).padStart(2, "0");
      return `${{year}}-${{month}}-${{day}}`;
    }}

    function currentDateKey() {{
      return dateKey(new Date());
    }}

    function formatWesternTime(value) {{
      if (!value) return "";
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return value;
      return new Intl.DateTimeFormat("en-US", {{
        timeZone: DISPLAY_TIME_ZONE,
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
        timeZoneName: "short"
      }}).format(date);
    }}

    function scheduleTimeCell(row) {{
      const checkAfter = formatWesternTime(row.result_check_after_utc);
      const kickoff = formatWesternTime(row.kickoff_utc);
      if (!checkAfter && !kickoff) return "Date passed";
      const kickoffLine = kickoff ? `Kickoff ${{esc(kickoff)}}` : "";
      return `${{esc(checkAfter || "Date passed")}}<br><span class="muted">${{kickoffLine}}</span>`;
    }}

    function selectedDate() {{
      return document.getElementById("match-date").value;
    }}

    function matchesForDate(dateValue) {{
      if (!dateValue) return [];
      return DATA.knockout.filter(row => row.date === dateValue);
    }}

    function matchStatus(row) {{
      if (row.is_actual_result === "True" || row.actual_advancing_team) return ["Completed", "actual"];

      const today = currentDateKey();
      const rowDate = row.date || "";
      const now = new Date();
      const kickoff = row.kickoff_utc ? new Date(row.kickoff_utc) : null;
      const checkAfter = row.result_check_after_utc ? new Date(row.result_check_after_utc) : null;

      if (kickoff && checkAfter && now >= kickoff && now <= checkAfter) return ["Live", "live"];
      if (checkAfter && now > checkAfter) return ["Update due", "due"];
      if (rowDate === today) return ["Today", "today"];
      if (rowDate && rowDate > today) return ["Upcoming", "projected"];
      return ["Needs update", "due"];
    }}

    function statusCell(row) {{
      const [label, cls] = matchStatus(row);
      return `<span class="pill ${{cls}}">${{esc(label)}}</span>`;
    }}

    function contextLabel(reason) {{
      if (!reason) return "";
      const lower = String(reason).toLowerCase();
      if (lower.includes("automatic knockout strength adjustment")) return "Performance boost";
      if (lower.includes("availability") || lower.includes("injur") || lower.includes("suspension") || lower.includes("red card")) return "Availability update";
      return "Context update";
    }}

    function contextSummary(row) {{
      const labels = [];
      if (row.team1_context_reason) labels.push(`${{row.team1}}: ${{contextLabel(row.team1_context_reason)}}`);
      if (row.team2_context_reason) labels.push(`${{row.team2}}: ${{contextLabel(row.team2_context_reason)}}`);
      return labels.join(" | ");
    }}

    function evaluationFor(row) {{
      if (!DATA || !DATA.evaluation) return null;
      return DATA.evaluation.find(item => item.match_number === row.match_number) || null;
    }}

    function evaluationCell(row) {{
      const evaluation = evaluationFor(row);
      if (!evaluation) return "<span class='muted'>Pending</span>";
      const cls = evaluation.evaluation === "Miss" ? "miss" : "actual";
      return `<span class="pill ${{cls}}">${{esc(evaluation.evaluation)}}</span><br><span class="muted">${{esc(evaluation.predicted_advancing_team)}} → ${{esc(evaluation.actual_advancing_team)}}</span>`;
    }}

    function playerCell(row) {{
      const hasPlayerData = row.team1_player_strength || row.team2_player_strength;
      if (!hasPlayerData) return "<span class='muted'>No data</span>";
      return `${{esc(row.team1_player_adjustment || "0.0")}}<br>${{esc(row.team2_player_adjustment || "0.0")}}`;
    }}

    function powerCell(row) {{
      const hasPowerData = row.team1_power_score || row.team2_power_score;
      if (!hasPowerData) return "<span class='muted'>No data</span>";
      return `${{esc(row.team1_power_adjustment || "0.0")}}<br>${{esc(row.team2_power_adjustment || "0.0")}}`;
    }}

    function networkCell(row) {{
      const hasNetworkData = row.team1_network_score || row.team2_network_score;
      if (!hasNetworkData) return "<span class='muted'>No data</span>";
      return `${{esc(row.team1_network_adjustment || "0.0")}}<br>${{esc(row.team2_network_adjustment || "0.0")}}`;
    }}

    function signed(value) {{
      const number = Number(value || 0);
      return `${{number >= 0 ? "+" : ""}}${{number.toFixed(1)}}`;
    }}

    function esc(value) {{
      return String(value ?? "").replace(/[&<>"']/g, ch => ({{
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      }}[ch]));
    }}

    function renderSummary() {{
      const final = DATA.final || {{}};
      const todayRows = matchesForDate(currentDateKey());
      const todayText = todayRows.length
        ? todayRows.map(row => `${{row.team1}} vs ${{row.team2}}`).join(" | ")
        : "No knockout match listed";
      const metrics = [
        ["Champion", DATA.projected_champion || "TBD"],
        ["Final", final.team1 && final.team2 ? `${{final.team1}} vs ${{final.team2}}` : "TBD"],
        ["Final Advance", final.team1_advance_probability ? `${{final.team1}} ${{fmtPct(final.team1_advance_probability)}} / ${{final.team2}} ${{fmtPct(final.team2_advance_probability)}}` : "TBD"],
        ["Today", todayText],
        ["Prediction Record", `${{DATA.prediction_hit_count || 0}} hit / ${{DATA.prediction_miss_count || 0}} miss`],
      ];
      document.getElementById("summary").innerHTML = metrics.map(([label, value]) => `
        <div class="metric">
          <div class="metric-label">${{esc(label)}}</div>
          <div class="metric-value">${{esc(value)}}</div>
        </div>
      `).join("");
    }}

    function renderRoundButtons() {{
      const container = document.getElementById("rounds");
      container.style.display = currentTab === "knockout" ? "flex" : "none";
      container.innerHTML = rounds.map(round => `
        <button type="button" class="${{round === currentRound ? "active" : ""}}" data-round="${{esc(round)}}">${{esc(round)}}</button>
      `).join("");
      container.querySelectorAll("button").forEach(button => {{
        button.addEventListener("click", () => {{
          currentRound = button.dataset.round;
          render();
        }});
      }});
    }}

    function rowMatches(row, query) {{
      if (!query) return true;
      return Object.values(row).join(" ").toLowerCase().includes(query);
    }}

    function renderKnockout() {{
      const query = document.getElementById("search").value.trim().toLowerCase();
      const dateFilter = selectedDate();
      let rows = DATA.knockout;
      if (currentRound !== "All") rows = rows.filter(row => row.round === currentRound);
      if (dateFilter) rows = rows.filter(row => row.date === dateFilter);
      rows = rows.filter(row => rowMatches(row, query));

      document.getElementById("thead").innerHTML = `
        <tr>
          <th>Match</th><th>Status</th><th>Date</th><th>Check After</th><th>Teams</th><th>Score</th><th>Actual</th>
          <th>90 Min</th><th>Advance</th><th>Projected</th><th>Adjusted Elo</th><th>Player</th><th>Power</th><th>Network</th><th>Context</th><th>Eval</th>
        </tr>`;
      document.getElementById("tbody").innerHTML = rows.map(row => `
        <tr class="${{evaluationFor(row)?.evaluation === "Miss" ? "miss" : row.is_actual_result === "True" ? "actual" : ""}}">
          <td><span class="muted">${{esc(row.round)}}</span><br><strong>#${{esc(row.match_number)}}</strong></td>
          <td>${{statusCell(row)}}</td>
          <td>${{esc(row.date)}}<br><span class="muted">${{esc(row.venue)}}</span></td>
          <td>${{scheduleTimeCell(row)}}</td>
          <td><span class="team">${{esc(row.team1)}}</span><br><span class="team">${{esc(row.team2)}}</span></td>
          <td>${{esc(score(row)) || "<span class='muted'>Pending</span>"}}</td>
          <td>${{row.actual_advancing_team ? `<span class="pill actual">${{esc(row.actual_advancing_team)}}</span>` : "<span class='muted'>Pending</span>"}}</td>
          <td>${{esc(row.predicted_90min_result)}}<br><span class="muted">${{fmtPct(row.team1_90min_win_probability)}} / ${{fmtPct(row.draw_90min_probability)}} / ${{fmtPct(row.team2_90min_win_probability)}}</span></td>
          <td>${{esc(row.team1)}} ${{fmtPct(row.team1_advance_probability)}}<br>${{esc(row.team2)}} ${{fmtPct(row.team2_advance_probability)}}</td>
          <td><span class="pill projected">${{esc(row.projected_advancing_team)}}</span></td>
          <td>${{esc(row.team1_adjusted_elo)}}<br>${{esc(row.team2_adjusted_elo)}}</td>
          <td>${{playerCell(row)}}</td>
          <td>${{powerCell(row)}}</td>
          <td>${{networkCell(row)}}</td>
          <td class="reason">${{esc(contextSummary(row)) || "<span class='muted'>None</span>"}}</td>
          <td>${{evaluationCell(row)}}</td>
        </tr>
      `).join("");
    }}

    function renderGroup() {{
      const query = document.getElementById("search").value.trim().toLowerCase();
      const rows = DATA.group.filter(row => rowMatches(row, query));
      document.getElementById("thead").innerHTML = `
        <tr>
          <th>Date</th><th>Stage</th><th>Teams</th><th>Actual</th><th>Prediction</th>
          <th>Probabilities</th><th>Pre Elo</th><th>Post Elo</th>
        </tr>`;
      document.getElementById("tbody").innerHTML = rows.map(row => `
        <tr class="actual">
          <td>${{esc(row.date)}}<br><span class="muted">${{esc(row.venue)}}</span></td>
          <td>${{esc(row.stage)}}</td>
          <td><span class="team">${{esc(row.home_team)}}</span><br><span class="team">${{esc(row.away_team)}}</span></td>
          <td>${{esc(row.home_score)}}-${{esc(row.away_score)}}<br><span class="pill actual">${{esc(row.actual_winner)}}</span></td>
          <td>${{esc(row.predicted_result)}}</td>
          <td>${{fmtPct(row.home_win_probability)}} / ${{fmtPct(row.draw_probability)}} / ${{fmtPct(row.away_win_probability)}}</td>
          <td>${{esc(row.home_pre_elo)}}<br>${{esc(row.away_pre_elo)}}</td>
          <td>${{esc(row.home_post_elo)}}<br>${{esc(row.away_post_elo)}}</td>
        </tr>
      `).join("");
    }}

    function renderRuns() {{
      const query = document.getElementById("search").value.trim().toLowerCase();
      const rows = DATA.history.filter(row => rowMatches(row, query)).slice().reverse();
      document.getElementById("thead").innerHTML = `
        <tr><th>Timestamp</th><th>Run</th><th>Champion</th><th>Updates</th><th>Snapshot</th></tr>`;
      document.getElementById("tbody").innerHTML = rows.map(row => `
        <tr>
          <td>${{esc(formatWesternTime(row.timestamp) || row.timestamp)}}</td>
          <td>${{esc(row.run_type)}}<br><span class="muted">${{esc(row.run_id)}}</span></td>
          <td><span class="pill projected">${{esc(row.projected_champion)}}</span></td>
          <td>Results: ${{esc(row.match_result_updates)}}<br>Strength: ${{esc(row.strength_adjustments_applied)}}<br>News: ${{esc(row.news_adjustments_applied)}}</td>
          <td>${{esc(row.snapshot_path)}}</td>
        </tr>
      `).join("");
    }}

    function renderEvaluation() {{
      const query = document.getElementById("search").value.trim().toLowerCase();
      const rows = DATA.evaluation.filter(row => rowMatches(row, query)).slice().reverse();
      document.getElementById("thead").innerHTML = `
        <tr><th>Match</th><th>Teams</th><th>Prediction</th><th>Actual</th><th>Result</th><th>Surprise</th><th>Note</th></tr>`;
      document.getElementById("tbody").innerHTML = rows.map(row => `
        <tr class="${{row.evaluation === "Hit" ? "actual" : ""}}">
          <td><span class="muted">${{esc(row.round)}}</span><br><strong>#${{esc(row.match_number)}}</strong><br><span class="muted">${{esc(row.date)}}</span></td>
          <td><span class="team">${{esc(row.team1)}}</span><br><span class="team">${{esc(row.team2)}}</span></td>
          <td><span class="pill projected">${{esc(row.predicted_advancing_team)}}</span><br><span class="muted">${{esc(row.predicted_90min_result)}}</span></td>
          <td><span class="pill actual">${{esc(row.actual_advancing_team)}}</span><br><span class="muted">${{esc(row.actual_score)}}</span></td>
          <td>${{row.evaluation === "Hit" ? "<span class='pill actual'>Hit</span>" : "<span class='pill projected'>Miss</span>"}}</td>
          <td>${{fmtPct(row.surprise_score)}}<br><span class="muted">actual ${{fmtPct(row.actual_advance_probability)}}</span></td>
          <td class="reason">${{esc(row.note)}}</td>
        </tr>
      `).join("");
    }}

    function renderHighStakes() {{
      const query = document.getElementById("search").value.trim().toLowerCase();
      const rows = (DATA.high_stakes || []).filter(row => rowMatches(row, query));
      document.getElementById("thead").innerHTML = `
        <tr><th>Match</th><th>Teams</th><th>Base Model</th><th>High-Stakes Model</th><th>Pick</th><th>Feature Edges</th><th>Why</th></tr>`;
      document.getElementById("tbody").innerHTML = rows.map(row => `
        <tr>
          <td><span class="muted">${{esc(row.round)}}</span><br><strong>#${{esc(row.match_number)}}</strong><br><span class="muted">${{esc(row.date)}}</span></td>
          <td><span class="team">${{esc(row.team1)}}</span><br><span class="team">${{esc(row.team2)}}</span></td>
          <td>${{esc(row.team1)}} ${{fmtPct(row.base_team1_advance_probability)}}<br>${{esc(row.team2)}} ${{fmtPct(row.base_team2_advance_probability)}}</td>
          <td>${{esc(row.team1)}} ${{fmtPct(row.high_stakes_team1_advance_probability)}}<br>${{esc(row.team2)}} ${{fmtPct(row.high_stakes_team2_advance_probability)}}</td>
          <td><span class="pill projected">${{esc(row.high_stakes_pick)}}</span><br><span class="muted">${{esc(row.confidence)}}</span></td>
          <td>Elo ${{signed(row.adjusted_elo_gap)}}<br>Form ${{signed(row.recent_world_cup_form_gap)}}<br>Star ${{signed(row.star_power_gap)}}<br>Network ${{signed(row.network_gap)}}<br>Fatigue ${{signed(row.fatigue_gap)}}</td>
          <td class="reason">${{esc(row.rationale)}}</td>
        </tr>
      `).join("");
    }}

    function renderIntelligence() {{
      const query = document.getElementById("search").value.trim().toLowerCase();
      const rows = (DATA.intelligence || []).filter(row => rowMatches(row, query)).slice().reverse();
      document.getElementById("thead").innerHTML = `
        <tr><th>Match</th><th>Teams</th><th>Result</th><th>Signals</th><th>Adjustment</th><th>Status</th></tr>`;
      document.getElementById("tbody").innerHTML = rows.map(row => `
        <tr>
          <td><span class="muted">${{esc(row.round)}}</span><br><strong>#${{esc(row.match_number)}}</strong><br><span class="muted">${{esc(row.date)}}</span></td>
          <td><span class="team">${{esc(row.team1)}}</span><br><span class="team">${{esc(row.team2)}}</span></td>
          <td>${{esc(row.score)}}<br><span class="pill actual">${{esc(row.actual_advancing_team)}}</span></td>
          <td class="reason">${{esc(row.signals)}}</td>
          <td>${{esc(row.adjustment_team || "None")}}<br><span class="muted">${{esc(row.adjustment_points || "0")}}</span></td>
          <td><span class="pill projected">${{esc(row.status)}}</span><br><span class="muted">${{esc(row.active_until)}}</span></td>
        </tr>
      `).join("");
    }}

    function setTab(tab) {{
      currentTab = tab;
      document.querySelectorAll(".tabs button").forEach(button => button.classList.remove("active"));
      document.getElementById(`tab-${{tab === "group" ? "group" : tab === "runs" ? "runs" : tab === "evaluation" ? "evaluation" : tab === "high-stakes" ? "high-stakes" : tab === "intelligence" ? "intelligence" : "knockout"}}`).classList.add("active");
      render();
    }}

    function render() {{
      renderSummary();
      renderRoundButtons();
      if (currentTab === "group") renderGroup();
      else if (currentTab === "evaluation") renderEvaluation();
      else if (currentTab === "high-stakes") renderHighStakes();
      else if (currentTab === "intelligence") renderIntelligence();
      else if (currentTab === "runs") renderRuns();
      else renderKnockout();
    }}

    document.getElementById("tab-knockout").addEventListener("click", () => setTab("knockout"));
    document.getElementById("tab-evaluation").addEventListener("click", () => setTab("evaluation"));
    document.getElementById("tab-high-stakes").addEventListener("click", () => setTab("high-stakes"));
    document.getElementById("tab-intelligence").addEventListener("click", () => setTab("intelligence"));
    document.getElementById("tab-group").addEventListener("click", () => setTab("group"));
    document.getElementById("tab-runs").addEventListener("click", () => setTab("runs"));
    document.getElementById("search").addEventListener("input", render);
    document.getElementById("match-date").addEventListener("change", render);
    document.getElementById("clear-date").addEventListener("click", () => {{
      document.getElementById("match-date").value = "";
      render();
    }});
    document.getElementById("match-date").value = currentDateKey();

    render();
  </script>
</body>
</html>
"""


def main():
    data = build_dashboard_data()
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        f.write(render_html(data))
    print(f"[Dashboard]: Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
