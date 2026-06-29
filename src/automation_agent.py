import csv
import os
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone


BRACKET_FIELDS = [
    "round",
    "match_number",
    "date",
    "team1",
    "team2",
    "team1_source",
    "team2_source",
    "venue",
    "venue_country",
    "team1_score_90",
    "team2_score_90",
    "team1_score_final",
    "team2_score_final",
    "actual_advancing_team",
]

CONTEXT_FIELDS = [
    "team",
    "adjustment_points",
    "reason",
    "source",
    "active_from",
    "active_until",
]

NEWS_CANDIDATE_FIELDS = [
    "detected_at",
    "team",
    "source_match_number",
    "next_match_number",
    "event_type",
    "severity",
    "adjustment_points",
    "reason",
    "source",
    "active_from",
    "active_until",
    "status",
]

LOG_FIELDS = [
    "updated_at",
    "update_type",
    "target_file",
    "match_number",
    "team",
    "field",
    "old_value",
    "new_value",
    "source",
    "note",
]

MATCH_RESULT_FIELDS = [
    "match_number",
    "team1_score_90",
    "team2_score_90",
    "team1_score_final",
    "team2_score_final",
    "actual_advancing_team",
    "source",
]

SOURCE_FIELDS = [
    "source_type",
    "name",
    "url",
    "enabled",
]


class AutomatedUpdateAgent:
    """
    Harvests concrete updates, applies transparent CSV changes, and logs every
    automatic model input change.
    """

    MAJOR_NEGATIVE = (
        "ruled out",
        "out for",
        "torn",
        "acl",
        "broken",
        "fracture",
        "red card",
        "sent off",
        "suspended",
        "suspension",
    )
    MODERATE_NEGATIVE = (
        "injury",
        "injured",
        "doubtful",
        "doubt",
        "limped",
        "withdrawn",
        "hamstring",
        "ankle",
        "knee",
        "concussion",
    )
    POSITIVE = (
        "returns",
        "return",
        "fit",
        "cleared",
        "available",
        "back in training",
    )

    def __init__(
        self,
        bracket_csv="data/knockout_bracket.csv",
        context_csv="data/team_context_adjustments.csv",
        news_candidates_csv="data/news_adjustment_candidates.csv",
        match_results_csv="data/harvested_match_results.csv",
        update_log_csv="data/update_log.csv",
        sources_csv="data/automation_sources.csv",
    ):
        self.bracket_csv = bracket_csv
        self.context_csv = context_csv
        self.news_candidates_csv = news_candidates_csv
        self.match_results_csv = match_results_csv
        self.update_log_csv = update_log_csv
        self.sources_csv = sources_csv

    def run(self):
        self.ensure_files()
        result_updates = self.apply_match_result_updates()
        news_updates = self.collect_and_apply_post_match_news()
        return {
            "match_result_updates": result_updates,
            "news_adjustments_applied": news_updates,
        }

    def ensure_files(self):
        self.ensure_csv(self.context_csv, CONTEXT_FIELDS)
        self.ensure_csv(self.news_candidates_csv, NEWS_CANDIDATE_FIELDS)
        self.ensure_csv(self.match_results_csv, MATCH_RESULT_FIELDS)
        self.ensure_csv(self.update_log_csv, LOG_FIELDS)
        self.ensure_csv(self.sources_csv, SOURCE_FIELDS, [
            {
                "source_type": "post_match_news_rss",
                "name": "Google News RSS",
                "url": "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en",
                "enabled": "yes",
            },
            {
                "source_type": "match_results_csv",
                "name": "Optional normalized results CSV URL",
                "url": "",
                "enabled": "no",
            },
        ])

    def ensure_csv(self, path, fields, starter_rows=None):
        if os.path.exists(path):
            return
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            if starter_rows:
                writer.writerows(starter_rows)

    def apply_match_result_updates(self):
        updates = 0
        bracket_rows = self.read_csv(self.bracket_csv)
        result_rows = self.load_match_result_rows()

        for result in result_rows:
            match_number = result.get("match_number", "")
            if not match_number:
                continue
            bracket_row = self.find_match(bracket_rows, match_number)
            if not bracket_row:
                continue

            for field in MATCH_RESULT_FIELDS:
                if field in ("match_number", "source"):
                    continue
                new_value = result.get(field, "")
                if new_value == "":
                    continue
                old_value = bracket_row.get(field, "")
                if old_value == new_value:
                    continue
                bracket_row[field] = new_value
                updates += 1
                self.log_update(
                    "match_result",
                    self.bracket_csv,
                    match_number,
                    result.get("actual_advancing_team", ""),
                    field,
                    old_value,
                    new_value,
                    result.get("source", ""),
                    "Applied normalized harvested match result.",
                )

        if updates:
            self.write_csv(self.bracket_csv, BRACKET_FIELDS, bracket_rows)
        return updates

    def load_match_result_rows(self):
        rows = self.read_csv(self.match_results_csv)
        for source in self.enabled_sources("match_results_csv"):
            if not source.get("url"):
                continue
            rows.extend(self.fetch_csv(source["url"]))
        return rows

    def collect_and_apply_post_match_news(self):
        applied = 0
        bracket_rows = self.read_csv(self.bracket_csv)
        context_rows = self.read_csv(self.context_csv)
        candidate_rows = self.read_csv(self.news_candidates_csv)

        existing_context_keys = {
            self.context_key(row)
            for row in context_rows
        }
        existing_candidate_keys = {
            self.candidate_key(row)
            for row in candidate_rows
        }

        for completed_match in bracket_rows:
            advancing_team = completed_match.get("actual_advancing_team", "")
            if not advancing_team:
                continue
            next_match = self.find_next_match(bracket_rows, completed_match["match_number"])
            if not next_match:
                continue

            items = self.fetch_news_items(advancing_team, completed_match["match_number"])
            for item in items:
                candidate = self.news_item_to_candidate(
                    item,
                    advancing_team,
                    completed_match,
                    next_match,
                )
                if not candidate:
                    continue
                if self.candidate_key(candidate) not in existing_candidate_keys:
                    candidate_rows.append(candidate)
                    existing_candidate_keys.add(self.candidate_key(candidate))

                context_row = {
                    "team": candidate["team"],
                    "adjustment_points": candidate["adjustment_points"],
                    "reason": candidate["reason"],
                    "source": candidate["source"],
                    "active_from": candidate["active_from"],
                    "active_until": candidate["active_until"],
                }
                if self.context_key(context_row) in existing_context_keys:
                    continue

                context_rows.append(context_row)
                existing_context_keys.add(self.context_key(context_row))
                applied += 1
                self.log_update(
                    "news_context",
                    self.context_csv,
                    next_match["match_number"],
                    candidate["team"],
                    "adjustment_points",
                    "",
                    candidate["adjustment_points"],
                    candidate["source"],
                    candidate["reason"],
                )

        if applied:
            self.write_csv(self.context_csv, CONTEXT_FIELDS, context_rows)
        if candidate_rows:
            self.write_csv(self.news_candidates_csv, NEWS_CANDIDATE_FIELDS, candidate_rows)
        return applied

    def fetch_news_items(self, team, match_number):
        query = f'"{team}" "World Cup" injury suspension "red card" match {match_number}'
        encoded_query = urllib.parse.quote(query)
        items = []

        sources = self.enabled_sources("post_match_news_rss")
        if not sources:
            sources = [{
                "url": "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en",
            }]

        for source in sources:
            url_template = source.get("url", "")
            if not url_template:
                continue
            url = url_template.format(query=encoded_query)
            try:
                with urllib.request.urlopen(url, timeout=20) as response:
                    body = response.read()
            except OSError:
                continue

            try:
                root = ET.fromstring(body)
            except ET.ParseError:
                continue

            for item in root.findall(".//item"):
                title = self.xml_text(item, "title")
                link = self.xml_text(item, "link")
                description = self.xml_text(item, "description")
                items.append({
                    "title": title,
                    "link": link,
                    "description": description,
                })

        return items

    def news_item_to_candidate(self, item, team, completed_match, next_match):
        text = f"{item.get('title', '')} {item.get('description', '')}".lower()
        if team.lower() not in text:
            return None

        event_type = ""
        severity = ""
        points = 0
        if self.contains_any(text, self.MAJOR_NEGATIVE):
            event_type = "availability_loss"
            severity = "major"
            points = -45
        elif self.contains_any(text, self.MODERATE_NEGATIVE):
            event_type = "availability_risk"
            severity = "moderate"
            points = -25
        elif self.contains_any(text, self.POSITIVE):
            event_type = "availability_boost"
            severity = "moderate"
            points = 20
        else:
            return None

        title = item.get("title", "").strip()
        if not title:
            return None

        return {
            "detected_at": self.now(),
            "team": team,
            "source_match_number": completed_match["match_number"],
            "next_match_number": next_match["match_number"],
            "event_type": event_type,
            "severity": severity,
            "adjustment_points": str(points),
            "reason": title,
            "source": item.get("link", ""),
            "active_from": completed_match["date"],
            "active_until": next_match["date"],
            "status": "auto_applied",
        }

    def find_next_match(self, bracket_rows, completed_match_number):
        winner_source = f"Winner match {completed_match_number}"
        for row in bracket_rows:
            if row.get("team1_source") == winner_source or row.get("team2_source") == winner_source:
                return row
        return None

    def find_match(self, rows, match_number):
        for row in rows:
            if row.get("match_number") == str(match_number):
                return row
        return None

    def enabled_sources(self, source_type):
        sources = []
        for row in self.read_csv(self.sources_csv):
            if row.get("source_type") != source_type:
                continue
            if row.get("enabled", "").strip().lower() not in ("yes", "true", "1"):
                continue
            sources.append(row)
        return sources

    def fetch_csv(self, url):
        try:
            with urllib.request.urlopen(url, timeout=20) as response:
                text = response.read().decode("utf-8")
        except OSError:
            return []
        return list(csv.DictReader(text.splitlines()))

    def read_csv(self, path):
        if not os.path.exists(path):
            return []
        with open(path, newline="") as f:
            return list(csv.DictReader(f))

    def write_csv(self, path, fieldnames, rows):
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def log_update(
        self,
        update_type,
        target_file,
        match_number,
        team,
        field,
        old_value,
        new_value,
        source,
        note,
    ):
        rows = self.read_csv(self.update_log_csv)
        rows.append({
            "updated_at": self.now(),
            "update_type": update_type,
            "target_file": target_file,
            "match_number": match_number,
            "team": team,
            "field": field,
            "old_value": old_value,
            "new_value": new_value,
            "source": source,
            "note": note,
        })
        self.write_csv(self.update_log_csv, LOG_FIELDS, rows)

    def context_key(self, row):
        return (
            row.get("team", ""),
            row.get("adjustment_points", ""),
            row.get("reason", ""),
            row.get("source", ""),
            row.get("active_until", ""),
        )

    def candidate_key(self, row):
        return (
            row.get("team", ""),
            row.get("next_match_number", ""),
            row.get("reason", ""),
            row.get("source", ""),
        )

    def contains_any(self, text, needles):
        return any(needle in text for needle in needles)

    def xml_text(self, item, tag):
        value = item.find(tag)
        if value is None or value.text is None:
            return ""
        return value.text

    def now(self):
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
