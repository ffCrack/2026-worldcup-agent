import csv
import html
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, date, timezone, timedelta


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
    "kickoff_utc",
    "result_check_after_utc",
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

RESULT_CHECK_FIELDS = [
    "match_number",
    "kickoff_utc",
    "check_after_utc",
    "source",
    "note",
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
        result_check_schedule_csv="data/result_check_schedule.csv",
        predictions_csv="data/knockout_bracket_predictions.csv",
    ):
        self.bracket_csv = bracket_csv
        self.context_csv = context_csv
        self.news_candidates_csv = news_candidates_csv
        self.match_results_csv = match_results_csv
        self.update_log_csv = update_log_csv
        self.sources_csv = sources_csv
        self.result_check_schedule_csv = result_check_schedule_csv
        self.predictions_csv = predictions_csv

    def run(self):
        self.ensure_files()
        harvested_results = self.harvest_ready_match_results()
        result_updates = self.apply_match_result_updates()
        strength_updates = self.apply_performance_context_adjustments()
        news_updates = self.collect_and_apply_post_match_news()
        return {
            "news_results_harvested": harvested_results,
            "match_result_updates": result_updates,
            "strength_adjustments_applied": strength_updates,
            "news_adjustments_applied": news_updates,
        }

    def ensure_files(self):
        self.ensure_csv(self.context_csv, CONTEXT_FIELDS)
        self.ensure_csv(self.news_candidates_csv, NEWS_CANDIDATE_FIELDS)
        self.ensure_csv(self.match_results_csv, MATCH_RESULT_FIELDS)
        self.ensure_csv(self.update_log_csv, LOG_FIELDS)
        self.ensure_csv(self.result_check_schedule_csv, RESULT_CHECK_FIELDS)
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

    def harvest_ready_match_results(self):
        bracket_rows = self.read_csv(self.bracket_csv)
        result_rows = self.read_csv(self.match_results_csv)
        schedule = {
            row.get("match_number", ""): row
            for row in self.read_csv(self.result_check_schedule_csv)
        }
        existing_results = {
            row.get("match_number", "")
            for row in result_rows
            if row.get("actual_advancing_team") or row.get("team1_score_90")
        }
        now = datetime.now(timezone.utc)
        harvested = 0

        for match in bracket_rows:
            match_number = match.get("match_number", "")
            if not match_number or match.get("actual_advancing_team") or match_number in existing_results:
                continue
            if not self.is_result_check_ready(match, schedule.get(match_number), now):
                continue

            result = self.harvest_match_result_from_news(match)
            if not result:
                continue

            result_rows.append(result)
            existing_results.add(match_number)
            harvested += 1
            self.log_update(
                "news_result_harvest",
                self.match_results_csv,
                match_number,
                result.get("actual_advancing_team", ""),
                "actual_advancing_team",
                "",
                result.get("actual_advancing_team", ""),
                result.get("source", ""),
                "Harvested a completed match result from post-match news.",
            )

        if harvested:
            self.write_csv(self.match_results_csv, MATCH_RESULT_FIELDS, result_rows)
        return harvested

    def is_result_check_ready(self, match, schedule_row, now):
        bracket_check_after = self.parse_utc_datetime(match.get("result_check_after_utc", ""))
        if bracket_check_after:
            return now >= bracket_check_after

        bracket_kickoff = self.parse_utc_datetime(match.get("kickoff_utc", ""))
        if bracket_kickoff:
            return now >= bracket_kickoff + timedelta(minutes=150)

        if schedule_row:
            check_after = self.parse_utc_datetime(schedule_row.get("check_after_utc", ""))
            if check_after:
                return now >= check_after
            kickoff = self.parse_utc_datetime(schedule_row.get("kickoff_utc", ""))
            if kickoff:
                return now >= kickoff + timedelta(minutes=150)

        # Fallback for rows that only have a date: check after the match date has fully passed.
        try:
            match_date = date.fromisoformat(match.get("date", ""))
        except ValueError:
            return False
        return now.date() > match_date

    def parse_utc_datetime(self, value):
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def harvest_match_result_from_news(self, match):
        team1 = match.get("team1", "")
        team2 = match.get("team2", "")
        if not team1 or not team2:
            return None

        queries = [
            f'"{team1}" "{team2}" "World Cup" score result',
            f'"{team1}" "{team2}" "World Cup" penalties advanced',
            f'"{team1}" "{team2}" "World Cup" live',
        ]
        for query in queries:
            for item in self.fetch_google_news(query):
                parsed = self.parse_match_result_item(item, team1, team2)
                if parsed:
                    source = item.get("link", "")
                    return {
                        "match_number": match["match_number"],
                        "team1_score_90": parsed["team1_score"],
                        "team2_score_90": parsed["team2_score"],
                        "team1_score_final": parsed.get("team1_score_final", ""),
                        "team2_score_final": parsed.get("team2_score_final", ""),
                        "actual_advancing_team": parsed["advancing_team"],
                        "source": source,
                    }
        return None

    def fetch_google_news(self, query):
        encoded_query = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
        try:
            with urllib.request.urlopen(url, timeout=20) as response:
                body = response.read()
        except OSError:
            return []

        try:
            root = ET.fromstring(body)
        except ET.ParseError:
            return []

        items = []
        for item in root.findall(".//item"):
            items.append({
                "title": html.unescape(self.xml_text(item, "title")),
                "link": self.xml_text(item, "link"),
                "description": html.unescape(self.strip_tags(self.xml_text(item, "description"))),
            })
        return items

    def parse_match_result_item(self, item, team1, team2):
        text = f"{item.get('title', '')} {item.get('description', '')}"
        compact_text = self.normalize_text(text)
        team1_norm = self.normalize_text(team1)
        team2_norm = self.normalize_text(team2)
        score = self.extract_score(compact_text, team1_norm, team2_norm)
        if not score:
            return None

        team1_score, team2_score = score
        advancing_team = self.advancing_team_from_text(compact_text, team1, team2, team1_score, team2_score)
        if not advancing_team:
            return None

        return {
            "team1_score": str(team1_score),
            "team2_score": str(team2_score),
            "advancing_team": advancing_team,
        }

    def extract_score(self, text, team1, team2):
        patterns = [
            rf"{re.escape(team1)}\D{{0,40}}(\d+)\s*[-:]\s*(\d+)\D{{0,40}}{re.escape(team2)}",
            rf"{re.escape(team2)}\D{{0,40}}(\d+)\s*[-:]\s*(\d+)\D{{0,40}}{re.escape(team1)}",
            rf"(\d+)\s*[-:]\s*(\d+)\D{{0,40}}{re.escape(team1)}\D{{0,40}}{re.escape(team2)}",
        ]
        for index, pattern in enumerate(patterns):
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue
            first = int(match.group(1))
            second = int(match.group(2))
            if index == 1:
                return second, first
            return first, second

        score_match = re.search(r"\b(\d+)\s*[-:]\s*(\d+)\b", text)
        if not score_match or team1 not in text or team2 not in text:
            return None
        first = int(score_match.group(1))
        second = int(score_match.group(2))
        team1_index = text.find(team1)
        team2_index = text.find(team2)
        if team2_index < team1_index:
            return second, first
        return first, second

    def advancing_team_from_text(self, text, team1, team2, team1_score, team2_score):
        if team1_score > team2_score:
            return team1
        if team2_score > team1_score:
            return team2

        team1_norm = self.normalize_text(team1)
        team2_norm = self.normalize_text(team2)
        advance_words = r"(advance|advanced|advances|beat|beats|defeat|defeats|knock out|knocks out|edge|edges)"
        if re.search(rf"{re.escape(team1_norm)}\D{{0,80}}{advance_words}", text):
            return team1
        if re.search(rf"{re.escape(team2_norm)}\D{{0,80}}{advance_words}", text):
            return team2
        if re.search(rf"{advance_words}\D{{0,80}}{re.escape(team1_norm)}", text):
            return team2
        if re.search(rf"{advance_words}\D{{0,80}}{re.escape(team2_norm)}", text):
            return team1
        return None

    def normalize_text(self, value):
        value = value.lower().replace("–", "-").replace("—", "-")
        value = re.sub(r"\s+", " ", value)
        return value.strip()

    def strip_tags(self, value):
        return re.sub(r"<[^>]+>", " ", value or "")

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

    def apply_performance_context_adjustments(self):
        applied = 0
        bracket_rows = self.read_csv(self.bracket_csv)
        prediction_rows = {
            row.get("match_number", ""): row
            for row in self.read_csv(self.predictions_csv)
        }
        result_sources = {
            row.get("match_number", ""): row.get("source", "")
            for row in self.load_match_result_rows()
        }
        context_rows = self.read_csv(self.context_csv)
        existing_keys = {
            self.performance_context_key(row)
            for row in context_rows
        }

        for completed_match in bracket_rows:
            advancing_team = completed_match.get("actual_advancing_team", "")
            if not advancing_team:
                continue

            next_match = self.find_next_match(bracket_rows, completed_match["match_number"])
            if not next_match:
                continue

            prediction = prediction_rows.get(completed_match["match_number"], {})
            adjustment = self.performance_adjustment_row(
                completed_match,
                next_match,
                prediction,
                result_sources.get(completed_match["match_number"], ""),
            )
            if not adjustment:
                continue

            key = self.performance_context_key(adjustment)
            if key in existing_keys:
                continue

            context_rows.append(adjustment)
            existing_keys.add(key)
            applied += 1
            self.log_update(
                "performance_context",
                self.context_csv,
                next_match["match_number"],
                adjustment["team"],
                "adjustment_points",
                "",
                adjustment["adjustment_points"],
                adjustment["source"],
                adjustment["reason"],
            )

        if applied:
            self.write_csv(self.context_csv, CONTEXT_FIELDS, context_rows)
        return applied

    def performance_adjustment_row(self, completed_match, next_match, prediction, source):
        advancing_team = completed_match.get("actual_advancing_team", "")
        team1 = completed_match.get("team1", "")
        team2 = completed_match.get("team2", "")
        if advancing_team not in (team1, team2):
            return None

        if advancing_team == team1:
            opponent = team2
            advance_probability = self.float_value(prediction.get("team1_advance_probability"))
            team_adjusted_elo = self.float_value(prediction.get("team1_adjusted_elo"))
            opponent_adjusted_elo = self.float_value(prediction.get("team2_adjusted_elo"))
        else:
            opponent = team1
            advance_probability = self.float_value(prediction.get("team2_advance_probability"))
            team_adjusted_elo = self.float_value(prediction.get("team2_adjusted_elo"))
            opponent_adjusted_elo = self.float_value(prediction.get("team1_adjusted_elo"))

        predicted_advancing_team = prediction.get("predicted_advancing_team", "")
        points = 0.0
        reasons = []

        if predicted_advancing_team and predicted_advancing_team != advancing_team:
            points += 18
            reasons.append(f"advanced against model pick {predicted_advancing_team}")

        if advance_probability is not None and advance_probability < 0.5:
            probability_points = min(18, (0.5 - advance_probability) * 80)
            points += probability_points
            reasons.append(f"pre-match advance probability {advance_probability:.1%}")

        if team_adjusted_elo is not None and opponent_adjusted_elo is not None:
            rating_gap = opponent_adjusted_elo - team_adjusted_elo
            if rating_gap > 25:
                rating_points = min(22, rating_gap / 12)
                points += rating_points
                reasons.append(f"overcame {opponent}'s adjusted rating edge")

        if self.was_penalty_advancement(completed_match):
            points += 10
            reasons.append("advanced after penalties")
        elif self.was_extra_time_advancement(completed_match):
            points += 8
            reasons.append("won after extra time")
        elif self.was_regulation_upset(completed_match, advancing_team, team_adjusted_elo, opponent_adjusted_elo):
            points += 6
            reasons.append("won in regulation against a stronger-rated opponent")

        if points < 10:
            return None

        points = int(round(min(points, 45)))
        reason = f"Automatic knockout strength adjustment after Match {completed_match['match_number']}: "
        reason += "; ".join(reasons)

        return {
            "team": advancing_team,
            "adjustment_points": str(points),
            "reason": reason,
            "source": source or "automated_performance_adjustment",
            "active_from": completed_match["date"],
            "active_until": next_match["date"],
        }

    def was_penalty_advancement(self, match):
        team1_final = self.int_value(match.get("team1_score_final"))
        team2_final = self.int_value(match.get("team2_score_final"))
        team1_90 = self.int_value(match.get("team1_score_90"))
        team2_90 = self.int_value(match.get("team2_score_90"))
        if team1_final is not None and team2_final is not None:
            return team1_final == team2_final
        if team1_90 is not None and team2_90 is not None:
            return team1_90 == team2_90
        return False

    def was_extra_time_advancement(self, match):
        team1_final = self.int_value(match.get("team1_score_final"))
        team2_final = self.int_value(match.get("team2_score_final"))
        team1_90 = self.int_value(match.get("team1_score_90"))
        team2_90 = self.int_value(match.get("team2_score_90"))
        if None in (team1_final, team2_final, team1_90, team2_90):
            return False
        return team1_90 == team2_90 and team1_final != team2_final

    def was_regulation_upset(self, match, advancing_team, team_adjusted_elo, opponent_adjusted_elo):
        team1_90 = self.int_value(match.get("team1_score_90"))
        team2_90 = self.int_value(match.get("team2_score_90"))
        if team1_90 is None or team2_90 is None or team1_90 == team2_90:
            return False
        if team_adjusted_elo is None or opponent_adjusted_elo is None:
            return False
        return advancing_team and team_adjusted_elo < opponent_adjusted_elo

    def float_value(self, value):
        if value in (None, ""):
            return None
        try:
            return float(value)
        except ValueError:
            return None

    def int_value(self, value):
        if value in (None, ""):
            return None
        try:
            return int(value)
        except ValueError:
            return None

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

    def performance_context_key(self, row):
        return (
            row.get("team", ""),
            row.get("source", ""),
            row.get("active_from", ""),
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
