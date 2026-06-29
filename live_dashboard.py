import argparse
import json
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from automate import main as run_automated_update
from generate_dashboard import build_dashboard_data


STATE = {
    "auto_update": True,
    "interval_seconds": 15 * 60,
    "last_update_started": "",
    "last_update_finished": "",
    "last_update_error": "",
    "last_dashboard_read": "",
    "update_count": 0,
    "is_updating": False,
}

STATE_LOCK = threading.Lock()


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
      <button id="tabGroup" type="button">Group History</button>
      <button id="tabRuns" type="button">Run History</button>
      <select id="roundFilter"></select>
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
      if (!s1 || !s2) return "";
      return `${s1}-${s2}`;
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
      document.getElementById("subtitle").textContent = `Dashboard read at ${STATUS.last_dashboard_read || "never"}`;
      document.getElementById("status").innerHTML = `
        <div><div class="muted">Updater</div><strong>${STATUS.auto_update ? "On" : "Off"}</strong></div>
        <div><div class="muted">Last Started</div><strong>${esc(STATUS.last_update_started || "Not yet")}</strong></div>
        <div><div class="muted">Last Finished</div><strong>${esc(STATUS.last_update_finished || "Not yet")}</strong></div>
        <div><div class="muted">Last Error</div><strong>${err}</strong></div>
      `;
    }
    function renderMetrics() {
      const final = DATA.final || {};
      const rows = [
        ["Champion", DATA.projected_champion || "TBD"],
        ["Final", final.team1 && final.team2 ? `${final.team1} vs ${final.team2}` : "TBD"],
        ["Final Odds", final.team1_advance_probability ? `${final.team1} ${pct(final.team1_advance_probability)} / ${final.team2} ${pct(final.team2_advance_probability)}` : "TBD"],
        ["Actual Knockouts", `${DATA.completed_knockout_count} / ${DATA.knockout.length}`],
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
      let rows = DATA.knockout.filter(row => round === "All" || row.round === round).filter(rowMatches);
      document.getElementById("thead").innerHTML = `
        <tr><th>Match</th><th>Date</th><th>Teams</th><th>Score</th><th>Actual</th><th>90 Min</th><th>Advance</th><th>Projected</th><th>Context</th></tr>`;
      document.getElementById("tbody").innerHTML = rows.map(row => `
        <tr class="${row.is_actual_result === "True" ? "actual" : ""}">
          <td><span class="muted">${esc(row.round)}</span><br><strong>#${esc(row.match_number)}</strong></td>
          <td>${esc(row.date)}<br><span class="muted">${esc(row.venue)}</span></td>
          <td><span class="team">${esc(row.team1)}</span><br><span class="team">${esc(row.team2)}</span></td>
          <td>${esc(score(row)) || "<span class='muted'>Pending</span>"}</td>
          <td>${row.actual_advancing_team ? `<span class="pill actual-pill">${esc(row.actual_advancing_team)}</span>` : "<span class='muted'>Pending</span>"}</td>
          <td>${esc(row.predicted_90min_result)}<br><span class="muted">${pct(row.team1_90min_win_probability)} / ${pct(row.draw_90min_probability)} / ${pct(row.team2_90min_win_probability)}</span></td>
          <td>${esc(row.team1)} ${pct(row.team1_advance_probability)}<br>${esc(row.team2)} ${pct(row.team2_advance_probability)}</td>
          <td><span class="pill projected-pill">${esc(row.projected_advancing_team)}</span></td>
          <td class="reason">${esc([row.team1_context_reason, row.team2_context_reason].filter(Boolean).join(" | ")) || "<span class='muted'>None</span>"}</td>
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
    function renderRuns() {
      const rows = DATA.history.filter(rowMatches).slice().reverse();
      document.getElementById("thead").innerHTML = `
        <tr><th>Timestamp</th><th>Run</th><th>Champion</th><th>Updates</th><th>Snapshot</th></tr>`;
      document.getElementById("tbody").innerHTML = rows.map(row => `
        <tr>
          <td>${esc(row.timestamp)}</td>
          <td>${esc(row.run_type)}<br><span class="muted">${esc(row.run_id)}</span></td>
          <td><span class="pill projected-pill">${esc(row.projected_champion)}</span></td>
          <td>Results: ${esc(row.match_result_updates)}<br>News: ${esc(row.news_adjustments_applied)}</td>
          <td>${esc(row.snapshot_path)}</td>
        </tr>
      `).join("");
    }
    function setTab(nextTab) {
      tab = nextTab;
      document.querySelectorAll(".controls button:not(#runNow)").forEach(button => button.classList.remove("active"));
      document.getElementById(nextTab === "group" ? "tabGroup" : nextTab === "runs" ? "tabRuns" : "tabKnockout").classList.add("active");
      render();
    }
    function render() {
      if (!DATA || !STATUS) return;
      renderStatus();
      renderMetrics();
      renderRoundFilter();
      if (tab === "group") renderGroup();
      else if (tab === "runs") renderRuns();
      else renderKnockout();
    }
    document.getElementById("tabKnockout").addEventListener("click", () => setTab("knockout"));
    document.getElementById("tabGroup").addEventListener("click", () => setTab("group"));
    document.getElementById("tabRuns").addEventListener("click", () => setTab("runs"));
    document.getElementById("roundFilter").addEventListener("change", event => { round = event.target.value; render(); });
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
    parser.add_argument("--no-auto-update", action="store_true")
    return parser.parse_args()


def run_update_once():
    with STATE_LOCK:
        if STATE["is_updating"]:
            return
        STATE["is_updating"] = True
        STATE["last_update_started"] = datetime.now().isoformat(timespec="seconds")
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
            STATE["last_update_finished"] = datetime.now().isoformat(timespec="seconds")
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
        with STATE_LOCK:
            STATE["last_dashboard_read"] = datetime.now().isoformat(timespec="seconds")
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
        STATE["auto_update"] = not args.no_auto_update
        STATE["interval_seconds"] = max(args.interval_minutes, 1) * 60

    thread = threading.Thread(target=background_update_loop, daemon=True)
    thread.start()

    server = ThreadingHTTPServer((args.host, args.port), LiveDashboardHandler)
    print("=== LIVE WORLD CUP DASHBOARD ===")
    print(f"Open http://{args.host}:{args.port}")
    print(f"Auto update: {'on' if not args.no_auto_update else 'off'}")
    print(f"Interval: {args.interval_minutes} minutes")
    server.serve_forever()


if __name__ == "__main__":
    main()
