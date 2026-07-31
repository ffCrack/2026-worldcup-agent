import argparse
import csv
import json
import errno
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from automate import main as run_automated_update
from generate_dashboard import build_dashboard_data


STATE = {
    "auto_update": False,
    "interval_seconds": 15 * 60,
    "last_update_started": "",
    "last_update_finished": "",
    "last_update_error": "",
    "last_dashboard_read": "",
    "update_count": 0,
    "is_updating": False,
}

STATE_LOCK = threading.Lock()
BRACKET_CSV = "data/knockout_bracket.csv"
DUE_MATCH_COOLDOWN_SECONDS = 10 * 60


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_utc(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def seconds_since(value, now):
    parsed = parse_utc(value)
    if not parsed:
        return None
    return (now - parsed).total_seconds()


def has_due_unfinished_match(now):
    try:
        with open(BRACKET_CSV, newline="") as f:
            rows = list(csv.DictReader(f))
    except FileNotFoundError:
        return False

    for row in rows:
        if row.get("actual_advancing_team"):
            continue
        check_after = parse_utc(row.get("result_check_after_utc", ""))
        if check_after and now >= check_after:
            return True
    return False


def maybe_start_overdue_update():
    now = datetime.now(timezone.utc)
    with STATE_LOCK:
        if not STATE["auto_update"] or STATE["is_updating"]:
            return

        last_finished_age = seconds_since(STATE["last_update_finished"], now)
        last_started_age = seconds_since(STATE["last_update_started"], now)
        interval_due = last_finished_age is None or last_finished_age >= STATE["interval_seconds"]
        due_match_ready = has_due_unfinished_match(now)
        due_match_cooldown_ok = last_started_age is None or last_started_age >= DUE_MATCH_COOLDOWN_SECONDS

        if not interval_due and not (due_match_ready and due_match_cooldown_ok):
            return

    threading.Thread(target=run_update_once, daemon=True).start()


LIVE_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Live World Cup Dashboard</title>
  <style>
    :root {
      --bg: #f6f7f9;
      --panel: #ffffff;
      --text: #20242b;
      --muted: #667085;
      --line: #d8dee8;
      --accent: #176b87;
      --accent-soft: #e6f2f5;
      --ok: #217a4d;
      --warn: #9a5b00;
      --bad: #b42318;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    header {
      background: var(--panel);
      border-bottom: 1px solid var(--line);
      padding: 18px 22px;
      position: sticky;
      top: 0;
      z-index: 5;
    }
    .top {
      max-width: 1440px;
      margin: 0 auto;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }
    h1 {
      margin: 0;
      font-size: 23px;
      letter-spacing: 0;
    }
    main {
      max-width: 1440px;
      margin: 0 auto;
      padding: 18px 22px 28px;
    }
    .controls {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      margin-bottom: 14px;
    }
    button, input, select {
      min-height: 36px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--text);
      padding: 0 10px;
      font: inherit;
      font-size: 14px;
    }
    button {
      cursor: pointer;
      font-weight: 700;
    }
    button.primary {
      background: var(--accent);
      color: #fff;
      border-color: var(--accent);
    }
    button.active {
      background: var(--accent-soft);
      border-color: #a6cfda;
      color: #134e63;
    }
    input { width: min(360px, 100%); }
    .metrics {
      display: grid;
      grid-template-columns: repeat(4, minmax(150px, 1fr));
      gap: 12px;
      margin-bottom: 14px;
    }
    .metric, .status {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 13px;
    }
    .metric-label, .muted {
      color: var(--muted);
      font-size: 12px;
    }
    .metric-value {
      margin-top: 7px;
      font-size: 21px;
      font-weight: 780;
      overflow-wrap: anywhere;
    }
    .status {
      display: grid;
      grid-template-columns: repeat(4, minmax(140px, 1fr));
      gap: 10px;
      margin-bottom: 14px;
      font-size: 13px;
    }
    .table-wrap {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: auto;
    }
    table {
      width: 100%;
      min-width: 1120px;
      border-collapse: collapse;
    }
    th, td {
      border-bottom: 1px solid var(--line);
      padding: 10px 12px;
      text-align: left;
      vertical-align: top;
      font-size: 13px;
      white-space: nowrap;
    }
    th {
      background: #eef3f6;
      color: #344054;
      position: sticky;
      top: 0;
      z-index: 1;
    }
    tr.actual td { background: #f0f8f4; }
    tr.miss td { background: #fff1f0; }
    .team { font-weight: 760; }
    .pill {
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      padding: 2px 8px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: #fff;
      font-size: 12px;
      font-weight: 760;
    }
    .actual-pill { color: var(--ok); border-color: #b7dfc9; background: #edf8f2; }
    .projected-pill { color: var(--warn); border-color: #ead2a8; background: #fff8ea; }
    .miss-pill { color: var(--bad); border-color: #f3b8b1; background: #fff1f0; }
    .live-pill { color: #134e63; border-color: #8fc5d2; background: #e6f2f5; }
    .due-pill { color: var(--bad); border-color: #f3b8b1; background: #fff1f0; }
    .today-pill { color: var(--warn); border-color: #ead2a8; background: #fff8ea; }
    .bad { color: var(--bad); }
    .reason { max-width: 360px; white-space: normal; color: var(--muted); }
    @media (max-width: 900px) {
      header, main { padding-left: 14px; padding-right: 14px; }
      .top { align-items: flex-start; flex-direction: column; }
      .metrics, .status { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
  </style>
</head>
<body>
  <header>
    <div class="top">
      <div>
        <h1>Live World Cup Dashboard</h1>
        <div class="muted" id="subtitle">Loading...</div>
      </div>
      <button class="primary" id="runNow" type="button">Run Update Now</button>
    </div>
  </header>
  <main>
    <section class="status" id="status"></section>
    <section class="metrics" id="metrics"></section>
    <div class="controls">
      <button class="active" id="tabKnockout" type="button">Knockout</button>
      <button id="tabEval" type="button">Evaluation</button>
      <button id="tabHighStakes" type="button">High Stakes</button>
      <button id="tabIntel" type="button">Intelligence</button>
      <button id="tabGroup" type="button">Group History</button>
      <button id="tabRuns" type="button">Run History</button>
      <select id="roundFilter"></select>
      <input id="matchDate" type="date" aria-label="Match date">
      <button id="clearDate" type="button">All Dates</button>
      <input id="search" type="search" placeholder="Search team, venue, round">
    </div>
    <section class="table-wrap">
      <table>
        <thead id="thead"></thead>
        <tbody id="tbody"></tbody>
      </table>
    </section>
  </main>
  <script>
    const DISPLAY_TIME_ZONE = "America/Los_Angeles";
    let DATA = null;
    let STATUS = null;
    let tab = "knockout";
    let round = "All";

    function esc(value) {
      return String(value ?? "").replace(/[&<>"']/g, ch => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      }[ch]));
    }
    function pct(value) {
      if (value === undefined || value === null || value === "") return "";
      return `${(Number(value) * 100).toFixed(1)}%`;
    }
    function score(row) {
      const s1 = row.team1_score_final || row.team1_score_90;
      const s2 = row.team2_score_final || row.team2_score_90;
      if (s1 === "" || s2 === "" || s1 === undefined || s2 === undefined) return "";
      return `${s1}-${s2}`;
    }
    function dateKey(date) {
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, "0");
      const day = String(date.getDate()).padStart(2, "0");
      return `${year}-${month}-${day}`;
    }
    function currentDateKey() {
      return dateKey(new Date());
    }
    function formatWesternTime(value) {
      if (!value) return "";
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return value;
      return new Intl.DateTimeFormat("en-US", {
        timeZone: DISPLAY_TIME_ZONE,
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
        timeZoneName: "short"
      }).format(date);
    }
    function scheduleTimeCell(row) {
      const checkAfter = formatWesternTime(row.result_check_after_utc);
      const kickoff = formatWesternTime(row.kickoff_utc);
      if (!checkAfter && !kickoff) return "Date passed";
      const kickoffLine = kickoff ? `Kickoff ${esc(kickoff)}` : "";
      return `${esc(checkAfter || "Date passed")}<br><span class="muted">${kickoffLine}</span>`;
    }
    function selectedDate() {
      return document.getElementById("matchDate").value;
    }
    function matchesForDate(dateValue) {
      if (!dateValue) return [];
      return DATA.knockout.filter(row => row.date === dateValue);
    }
    function matchStatus(row) {
      if (row.is_actual_result === "True" || row.actual_advancing_team) return ["Completed", "actual-pill"];

      const today = currentDateKey();
      const rowDate = row.date || "";
      const now = new Date();
      const kickoff = row.kickoff_utc ? new Date(row.kickoff_utc) : null;
      const checkAfter = row.result_check_after_utc ? new Date(row.result_check_after_utc) : null;

      if (kickoff && checkAfter && now >= kickoff && now <= checkAfter) return ["Live", "live-pill"];
      if (checkAfter && now > checkAfter) return ["Update due", "due-pill"];
      if (rowDate === today) return ["Today", "today-pill"];
      if (rowDate && rowDate > today) return ["Upcoming", "projected-pill"];
      return ["Needs update", "due-pill"];
    }
    function statusCell(row) {
      const [label, cls] = matchStatus(row);
      return `<span class="pill ${cls}">${esc(label)}</span>`;
    }
    function contextLabel(reason) {
      if (!reason) return "";
      const lower = String(reason).toLowerCase();
      if (lower.includes("automatic knockout strength adjustment")) return "Performance boost";
      if (lower.includes("availability") || lower.includes("injur") || lower.includes("suspension") || lower.includes("red card")) return "Availability update";
      return "Context update";
    }
    function contextSummary(row) {
      const labels = [];
      if (row.team1_context_reason) labels.push(`${row.team1}: ${contextLabel(row.team1_context_reason)}`);
      if (row.team2_context_reason) labels.push(`${row.team2}: ${contextLabel(row.team2_context_reason)}`);
      return labels.join(" | ");
    }
    function evaluationFor(row) {
      if (!DATA || !DATA.evaluation) return null;
      return DATA.evaluation.find(item => item.match_number === row.match_number) || null;
    }
    function evaluationCell(row) {
      const evaluation = evaluationFor(row);
      if (!evaluation) return "<span class='muted'>Pending</span>";
      const cls = evaluation.evaluation === "Miss" ? "miss-pill" : "actual-pill";
      return `<span class="pill ${cls}">${esc(evaluation.evaluation)}</span><br><span class="muted">${esc(evaluation.predicted_advancing_team)} → ${esc(evaluation.actual_advancing_team)}</span>`;
    }
    function playerCell(row) {
      const hasPlayerData = row.team1_player_strength || row.team2_player_strength;
      if (!hasPlayerData) return "<span class='muted'>No data</span>";
      return `${esc(row.team1_player_adjustment || "0.0")}<br>${esc(row.team2_player_adjustment || "0.0")}`;
    }
    function powerCell(row) {
      const hasPowerData = row.team1_power_score || row.team2_power_score;
      if (!hasPowerData) return "<span class='muted'>No data</span>";
      return `${esc(row.team1_power_adjustment || "0.0")}<br>${esc(row.team2_power_adjustment || "0.0")}`;
    }
    function networkCell(row) {
      const hasNetworkData = row.team1_network_score || row.team2_network_score;
      if (!hasNetworkData) return "<span class='muted'>No data</span>";
      return `${esc(row.team1_network_adjustment || "0.0")}<br>${esc(row.team2_network_adjustment || "0.0")}`;
    }
    function signed(value) {
      const number = Number(value || 0);
      return `${number >= 0 ? "+" : ""}${number.toFixed(1)}`;
    }
    function rowMatches(row) {
      const query = document.getElementById("search").value.trim().toLowerCase();
      if (!query) return true;
      return Object.values(row).join(" ").toLowerCase().includes(query);
    }
    async function refresh() {
      const response = await fetch("/api/data", { cache: "no-store" });
      const payload = await response.json();
      DATA = payload.data;
      STATUS = payload.status;
      render();
    }
    async function runNow() {
      const button = document.getElementById("runNow");
      button.disabled = true;
      button.textContent = "Updating...";
      await fetch("/api/run-now", { method: "POST" });
      await refresh();
      button.disabled = false;
      button.textContent = "Run Update Now";
    }
    function renderStatus() {
      const err = STATUS.last_update_error ? `<span class="bad">${esc(STATUS.last_update_error)}</span>` : "None";
      document.getElementById("subtitle").textContent = `Dashboard read at ${formatWesternTime(STATUS.last_dashboard_read) || "never"}`;
      document.getElementById("status").innerHTML = `
        <div><div class="muted">Updater</div><strong>${STATUS.auto_update ? "On" : "Off"}</strong></div>
        <div><div class="muted">Last Started</div><strong>${esc(formatWesternTime(STATUS.last_update_started) || "Not yet")}</strong></div>
        <div><div class="muted">Last Finished</div><strong>${esc(formatWesternTime(STATUS.last_update_finished) || "Not yet")}</strong></div>
        <div><div class="muted">Last Error</div><strong>${err}</strong></div>
      `;
    }
    function renderMetrics() {
      const final = DATA.final || {};
      const todayRows = matchesForDate(currentDateKey());
      const todayText = todayRows.length
        ? todayRows.map(row => `${row.team1} vs ${row.team2}`).join(" | ")
        : "No knockout match listed";
      const rows = [
        ["Champion", DATA.projected_champion || "TBD"],
        ["Final", final.team1 && final.team2 ? `${final.team1} vs ${final.team2}` : "TBD"],
        ["Final Odds", final.team1_advance_probability ? `${final.team1} ${pct(final.team1_advance_probability)} / ${final.team2} ${pct(final.team2_advance_probability)}` : "TBD"],
        ["Today", todayText],
        ["Prediction Record", `${DATA.prediction_hit_count || 0} hit / ${DATA.prediction_miss_count || 0} miss`],
      ];
      document.getElementById("metrics").innerHTML = rows.map(([label, value]) => `
        <div class="metric"><div class="metric-label">${esc(label)}</div><div class="metric-value">${esc(value)}</div></div>
      `).join("");
    }
    function renderRoundFilter() {
      const select = document.getElementById("roundFilter");
      const rounds = ["All", ...new Set(DATA.knockout.map(row => row.round).filter(Boolean))];
      select.style.display = tab === "knockout" ? "inline-block" : "none";
      select.innerHTML = rounds.map(item => `<option value="${esc(item)}"${item === round ? " selected" : ""}>${esc(item)}</option>`).join("");
    }
    function renderKnockout() {
      const dateFilter = selectedDate();
      let rows = DATA.knockout.filter(row => round === "All" || row.round === round);
      if (dateFilter) rows = rows.filter(row => row.date === dateFilter);
      rows = rows.filter(rowMatches);
      document.getElementById("thead").innerHTML = `
        <tr><th>Match</th><th>Status</th><th>Date</th><th>Check After</th><th>Teams</th><th>Score</th><th>Actual</th><th>90 Min</th><th>Advance</th><th>Projected</th><th>Player</th><th>Power</th><th>Network</th><th>Context</th><th>Eval</th></tr>`;
      document.getElementById("tbody").innerHTML = rows.map(row => `
        <tr class="${evaluationFor(row)?.evaluation === "Miss" ? "miss" : row.is_actual_result === "True" ? "actual" : ""}">
          <td><span class="muted">${esc(row.round)}</span><br><strong>#${esc(row.match_number)}</strong></td>
          <td>${statusCell(row)}</td>
          <td>${esc(row.date)}<br><span class="muted">${esc(row.venue)}</span></td>
          <td>${scheduleTimeCell(row)}</td>
          <td><span class="team">${esc(row.team1)}</span><br><span class="team">${esc(row.team2)}</span></td>
          <td>${esc(score(row)) || "<span class='muted'>Pending</span>"}</td>
          <td>${row.actual_advancing_team ? `<span class="pill actual-pill">${esc(row.actual_advancing_team)}</span>` : "<span class='muted'>Pending</span>"}</td>
          <td>${esc(row.predicted_90min_result)}<br><span class="muted">${pct(row.team1_90min_win_probability)} / ${pct(row.draw_90min_probability)} / ${pct(row.team2_90min_win_probability)}</span></td>
          <td>${esc(row.team1)} ${pct(row.team1_advance_probability)}<br>${esc(row.team2)} ${pct(row.team2_advance_probability)}</td>
          <td><span class="pill projected-pill">${esc(row.projected_advancing_team)}</span></td>
          <td>${playerCell(row)}</td>
          <td>${powerCell(row)}</td>
          <td>${networkCell(row)}</td>
          <td class="reason">${esc(contextSummary(row)) || "<span class='muted'>None</span>"}</td>
          <td>${evaluationCell(row)}</td>
        </tr>
      `).join("");
    }
    function renderGroup() {
      const rows = DATA.group.filter(rowMatches);
      document.getElementById("thead").innerHTML = `
        <tr><th>Date</th><th>Stage</th><th>Teams</th><th>Actual</th><th>Prediction</th><th>Probabilities</th><th>Elo Change</th></tr>`;
      document.getElementById("tbody").innerHTML = rows.map(row => `
        <tr class="actual">
          <td>${esc(row.date)}<br><span class="muted">${esc(row.venue)}</span></td>
          <td>${esc(row.stage)}</td>
          <td><span class="team">${esc(row.home_team)}</span><br><span class="team">${esc(row.away_team)}</span></td>
          <td>${esc(row.home_score)}-${esc(row.away_score)}<br><span class="pill actual-pill">${esc(row.actual_winner)}</span></td>
          <td>${esc(row.predicted_result)}</td>
          <td>${pct(row.home_win_probability)} / ${pct(row.draw_probability)} / ${pct(row.away_win_probability)}</td>
          <td>${esc(row.home_pre_elo)} -> ${esc(row.home_post_elo)}<br>${esc(row.away_pre_elo)} -> ${esc(row.away_post_elo)}</td>
        </tr>
      `).join("");
    }
    function renderEvaluation() {
      const rows = DATA.evaluation.filter(rowMatches).slice().reverse();
      document.getElementById("thead").innerHTML = `
        <tr><th>Match</th><th>Teams</th><th>Prediction</th><th>Actual</th><th>Result</th><th>Surprise</th><th>Note</th></tr>`;
      document.getElementById("tbody").innerHTML = rows.map(row => `
        <tr class="${row.evaluation === "Hit" ? "actual" : ""}">
          <td><span class="muted">${esc(row.round)}</span><br><strong>#${esc(row.match_number)}</strong><br><span class="muted">${esc(row.date)}</span></td>
          <td><span class="team">${esc(row.team1)}</span><br><span class="team">${esc(row.team2)}</span></td>
          <td><span class="pill projected-pill">${esc(row.predicted_advancing_team)}</span><br><span class="muted">${esc(row.predicted_90min_result)}</span></td>
          <td><span class="pill actual-pill">${esc(row.actual_advancing_team)}</span><br><span class="muted">${esc(row.actual_score)}</span></td>
          <td>${row.evaluation === "Hit" ? "<span class='pill actual-pill'>Hit</span>" : "<span class='pill projected-pill'>Miss</span>"}</td>
          <td>${pct(row.surprise_score)}<br><span class="muted">actual ${pct(row.actual_advance_probability)}</span></td>
          <td class="reason">${esc(row.note)}</td>
        </tr>
      `).join("");
    }
    function renderHighStakes() {
      const rows = (DATA.high_stakes || []).filter(rowMatches);
      document.getElementById("thead").innerHTML = `
        <tr><th>Match</th><th>Teams</th><th>Base Model</th><th>High-Stakes Model</th><th>Pick</th><th>Feature Edges</th><th>Why</th></tr>`;
      document.getElementById("tbody").innerHTML = rows.map(row => `
        <tr>
          <td><span class="muted">${esc(row.round)}</span><br><strong>#${esc(row.match_number)}</strong><br><span class="muted">${esc(row.date)}</span></td>
          <td><span class="team">${esc(row.team1)}</span><br><span class="team">${esc(row.team2)}</span></td>
          <td>${esc(row.team1)} ${pct(row.base_team1_advance_probability)}<br>${esc(row.team2)} ${pct(row.base_team2_advance_probability)}</td>
          <td>${esc(row.team1)} ${pct(row.high_stakes_team1_advance_probability)}<br>${esc(row.team2)} ${pct(row.high_stakes_team2_advance_probability)}</td>
          <td><span class="pill projected-pill">${esc(row.high_stakes_pick)}</span><br><span class="muted">${esc(row.confidence)}</span></td>
          <td>Elo ${signed(row.adjusted_elo_gap)}<br>Recent ${signed(row.recent_world_cup_form_gap)}<br>Knockout ${signed(row.knockout_form_gap)}<br>Defense ${signed(row.defensive_control_gap)}<br>Star ${signed(row.star_power_gap)}<br>Strategy ${signed(row.strategy_gap)}<br>Clutch ${signed(row.clutch_late_game_gap)}<br>Fatigue ${signed(row.fatigue_gap)}</td>
          <td class="reason">${esc(row.rationale)}</td>
        </tr>
      `).join("");
    }
    function renderIntelligence() {
      const rows = (DATA.intelligence || []).filter(rowMatches).slice().reverse();
      document.getElementById("thead").innerHTML = `
        <tr><th>Match</th><th>Teams</th><th>Result</th><th>Signals</th><th>Adjustment</th><th>Status</th></tr>`;
      document.getElementById("tbody").innerHTML = rows.map(row => `
        <tr>
          <td><span class="muted">${esc(row.round)}</span><br><strong>#${esc(row.match_number)}</strong><br><span class="muted">${esc(row.date)}</span></td>
          <td><span class="team">${esc(row.team1)}</span><br><span class="team">${esc(row.team2)}</span></td>
          <td>${esc(row.score)}<br><span class="pill actual-pill">${esc(row.actual_advancing_team)}</span></td>
          <td class="reason">${esc(row.signals)}</td>
          <td>${esc(row.adjustment_team || "None")}<br><span class="muted">${esc(row.adjustment_points || "0")}</span></td>
          <td><span class="pill projected-pill">${esc(row.status)}</span><br><span class="muted">${esc(row.active_until)}</span></td>
        </tr>
      `).join("");
    }
    function renderRuns() {
      const rows = DATA.history.filter(rowMatches).slice().reverse();
      document.getElementById("thead").innerHTML = `
        <tr><th>Timestamp</th><th>Run</th><th>Champion</th><th>Updates</th><th>Snapshot</th></tr>`;
      document.getElementById("tbody").innerHTML = rows.map(row => `
        <tr>
          <td>${esc(formatWesternTime(row.timestamp) || row.timestamp)}</td>
          <td>${esc(row.run_type)}<br><span class="muted">${esc(row.run_id)}</span></td>
          <td><span class="pill projected-pill">${esc(row.projected_champion)}</span></td>
          <td>Results: ${esc(row.match_result_updates)}<br>Strength: ${esc(row.strength_adjustments_applied)}<br>News: ${esc(row.news_adjustments_applied)}</td>
          <td>${esc(row.snapshot_path)}</td>
        </tr>
      `).join("");
    }
    function setTab(nextTab) {
      tab = nextTab;
      document.querySelectorAll(".controls button:not(#runNow)").forEach(button => button.classList.remove("active"));
      document.getElementById(nextTab === "group" ? "tabGroup" : nextTab === "runs" ? "tabRuns" : nextTab === "evaluation" ? "tabEval" : nextTab === "high-stakes" ? "tabHighStakes" : nextTab === "intelligence" ? "tabIntel" : "tabKnockout").classList.add("active");
      render();
    }
    function render() {
      if (!DATA || !STATUS) return;
      renderStatus();
      renderMetrics();
      renderRoundFilter();
      if (tab === "group") renderGroup();
      else if (tab === "evaluation") renderEvaluation();
      else if (tab === "high-stakes") renderHighStakes();
      else if (tab === "intelligence") renderIntelligence();
      else if (tab === "runs") renderRuns();
      else renderKnockout();
    }
    document.getElementById("tabKnockout").addEventListener("click", () => setTab("knockout"));
    document.getElementById("tabEval").addEventListener("click", () => setTab("evaluation"));
    document.getElementById("tabHighStakes").addEventListener("click", () => setTab("high-stakes"));
    document.getElementById("tabIntel").addEventListener("click", () => setTab("intelligence"));
    document.getElementById("tabGroup").addEventListener("click", () => setTab("group"));
    document.getElementById("tabRuns").addEventListener("click", () => setTab("runs"));
    document.getElementById("roundFilter").addEventListener("change", event => { round = event.target.value; render(); });
    document.getElementById("matchDate").addEventListener("change", render);
    document.getElementById("clearDate").addEventListener("click", () => {
      document.getElementById("matchDate").value = "";
      render();
    });
    document.getElementById("matchDate").value = currentDateKey();
    document.getElementById("search").addEventListener("input", render);
    document.getElementById("runNow").addEventListener("click", runNow);
    refresh();
    setInterval(refresh, 15000);
  </script>
</body>
</html>
"""


def parse_args():
    parser = argparse.ArgumentParser(description="Serve a live local World Cup dashboard.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--interval-minutes", type=float, default=15)
    parser.add_argument("--auto-update", action="store_true")
    parser.add_argument("--no-auto-update", action="store_true")
    return parser.parse_args()


def run_update_once():
    with STATE_LOCK:
        if STATE["is_updating"]:
            return
        STATE["is_updating"] = True
        STATE["last_update_started"] = utc_now()
        STATE["last_update_error"] = ""

    try:
        run_automated_update()
        with STATE_LOCK:
            STATE["update_count"] += 1
    except Exception as exc:
        with STATE_LOCK:
            STATE["last_update_error"] = str(exc)
    finally:
        with STATE_LOCK:
            STATE["last_update_finished"] = utc_now()
            STATE["is_updating"] = False


def background_update_loop():
    while True:
        with STATE_LOCK:
            enabled = STATE["auto_update"]
            interval = STATE["interval_seconds"]
        if enabled:
            run_update_once()
        time.sleep(interval)


class LiveDashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            self.send_html(LIVE_HTML)
            return
        if path == "/api/data":
            self.send_json(self.dashboard_payload())
            return
        self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/run-now":
            threading.Thread(target=run_update_once, daemon=True).start()
            self.send_json({"ok": True})
            return
        self.send_error(404)

    def dashboard_payload(self):
        maybe_start_overdue_update()
        with STATE_LOCK:
            STATE["last_dashboard_read"] = utc_now()
            status = dict(STATE)
        return {
            "data": build_dashboard_data(),
            "status": status,
        }

    def send_html(self, body):
        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def send_json(self, payload):
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, fmt, *args):
        return


def main():
    args = parse_args()
    with STATE_LOCK:
        STATE["auto_update"] = args.auto_update and not args.no_auto_update
        STATE["interval_seconds"] = max(args.interval_minutes, 1) * 60

    try:
        server = ThreadingHTTPServer((args.host, args.port), LiveDashboardHandler)
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            print("=== LIVE WORLD CUP DASHBOARD ===")
            print(f"Port {args.port} is already in use.")
            print(f"The dashboard may already be running at http://{args.host}:{args.port}")
            print("Stop the existing run, or start this one with a different port:")
            print("python3 live_dashboard.py --port 8766")
            return
        raise

    thread = threading.Thread(target=background_update_loop, daemon=True)
    thread.start()

    print("=== LIVE WORLD CUP DASHBOARD ===")
    print(f"Open http://{args.host}:{args.port}")
    print(f"Auto update: {'on' if STATE['auto_update'] else 'off'}")
    print(f"Interval: {args.interval_minutes} minutes")
    server.serve_forever()


if __name__ == "__main__":
    main()
