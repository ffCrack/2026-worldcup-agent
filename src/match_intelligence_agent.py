import csv
import os
from datetime import datetime, timezone


CONTEXT_FIELDS = [
    "team",
    "adjustment_points",
    "reason",
    "source",
    "active_from",
    "active_until",
]

NOTE_FIELDS = [
    "detected_at",
    "match_number",
    "round",
    "date",
    "team1",
    "team2",
    "score",
    "actual_advancing_team",
    "predicted_advancing_team",
    "actual_advance_probability",
    "signals",
    "adjustment_team",
    "adjustment_points",
    "adjustment_reason",
    "active_until",
    "source",
    "status",
]


class MatchIntelligenceAgent:
    """
    Deterministic post-match reasoning layer.

    This is agentic workflow, not an LLM agent: it reads model outputs and match
    results, converts visible match signals into transparent notes, and applies
    conservative context adjustments for the next match.
    """

    def __init__(
        self,
        predictions_csv="data/knockout_bracket_predictions.csv",
        context_csv="data/team_context_adjustments.csv",
        notes_csv="data/match_intelligence_notes.csv",
    ):
        self.predictions_csv = predictions_csv
        self.context_csv = context_csv
        self.notes_csv = notes_csv

    def run(self):
        predictions = self.read_csv(self.predictions_csv)
        completed = [
            row for row in predictions
            if row.get("actual_advancing_team")
        ]
        notes = self.read_csv(self.notes_csv)
        context_rows = self.read_csv(self.context_csv)

        notes_by_match = {
            row.get("match_number", ""): row
            for row in notes
            if row.get("match_number")
        }
        bootstrap_notes = not notes_by_match
        existing_context_keys = {
            self.context_key(row)
            for row in context_rows
        }

        completed_by_team = self.completed_matches_by_team(completed)
        applied = 0
        notes_written = 0

        for row in completed:
            note = self.analyze_match(row, completed_by_team)
            if not note:
                continue

            old_note = notes_by_match.get(note["match_number"])
            is_new_note = old_note is None
            if old_note and old_note.get("detected_at"):
                note["detected_at"] = old_note["detected_at"]
            if old_note != note:
                notes_by_match[note["match_number"]] = note
                notes_written += 1

            context = self.context_from_note(note) if is_new_note and not bootstrap_notes else None
            if not context:
                continue
            key = self.context_key(context)
            if key in existing_context_keys:
                continue
            context_rows.append(context)
            existing_context_keys.add(key)
            applied += 1

        self.write_csv(self.notes_csv, NOTE_FIELDS, sorted(
            notes_by_match.values(),
            key=lambda item: int(item.get("match_number") or 0),
        ))
        if applied:
            self.write_csv(self.context_csv, CONTEXT_FIELDS, context_rows)

        return {
            "match_intelligence_notes": notes_written,
            "match_intelligence_adjustments": applied,
        }

    def analyze_match(self, row, completed_by_team):
        actual = row.get("actual_advancing_team", "")
        if not actual:
            return None

        score_text = self.score(row)
        actual_probability = self.actual_advance_probability(row, actual)
        margin = self.margin(row)
        penalty = self.was_penalty_advancement(row)
        next_date = self.next_match_date(row)
        source = self.source_for_match(row)

        signals = []
        points = 0

        predicted = row.get("predicted_advancing_team", "")
        if predicted and predicted != actual:
            signals.append(f"upset over model pick {predicted}")
            points += 28

        if actual_probability is not None:
            if actual_probability < 0.35:
                signals.append(f"very low pre-match advance probability {actual_probability:.1%}")
                points += 18
            elif actual_probability < 0.5:
                signals.append(f"underdog advance probability {actual_probability:.1%}")
                points += 10
            elif actual_probability > 0.75 and margin is not None and margin <= 1:
                signals.append(f"hard win despite favorite probability {actual_probability:.1%}")
                points -= 14

        if penalty:
            signals.append("advanced after penalties")
            points += 8
        elif margin is not None:
            if margin >= 2 and actual_probability is not None and actual_probability >= 0.5:
                signals.append(f"controlled {margin}-goal win")
                points += min(18, 8 + margin * 4)
            elif margin == 1 and actual_probability is not None and actual_probability >= 0.65:
                signals.append("narrow one-goal win as clear favorite")
                points -= 8

        recent_hard_wins = self.recent_hard_wins(actual, completed_by_team)
        if recent_hard_wins >= 2:
            signals.append(f"{recent_hard_wins} consecutive hard knockout wins")
            points -= 12

        points = self.cap(points, -32, 42)
        adjustment_reason = ""
        status = "note_only"
        if points:
            adjustment_reason = self.adjustment_reason(row, signals)
            status = "context_candidate"

        return {
            "detected_at": self.now(),
            "match_number": row.get("match_number", ""),
            "round": row.get("round", ""),
            "date": row.get("date", ""),
            "team1": row.get("team1", ""),
            "team2": row.get("team2", ""),
            "score": score_text,
            "actual_advancing_team": actual,
            "predicted_advancing_team": predicted,
            "actual_advance_probability": "" if actual_probability is None else round(actual_probability, 4),
            "signals": " | ".join(signals) if signals else "no special signal",
            "adjustment_team": actual if points else "",
            "adjustment_points": str(points) if points else "",
            "adjustment_reason": adjustment_reason,
            "active_until": next_date,
            "source": source,
            "status": status,
        }

    def context_from_note(self, note):
        if not note.get("adjustment_team") or not note.get("adjustment_points"):
            return None
        if not note.get("active_until"):
            return None
        return {
            "team": note["adjustment_team"],
            "adjustment_points": note["adjustment_points"],
            "reason": f"Match intelligence after Match {note['match_number']}: {note['adjustment_reason']}",
            "source": note.get("source", "match_intelligence_agent"),
            "active_from": note.get("date", ""),
            "active_until": note.get("active_until", ""),
        }

    def adjustment_reason(self, row, signals):
        opponent = self.opponent(row, row.get("actual_advancing_team", ""))
        base = f"{row.get('actual_advancing_team')} vs {opponent}: "
        return base + "; ".join(signals)

    def completed_matches_by_team(self, completed):
        by_team = {}
        for row in completed:
            for team in (row.get("team1", ""), row.get("team2", "")):
                if team:
                    by_team.setdefault(team, []).append(row)
        for rows in by_team.values():
            rows.sort(key=lambda item: int(item.get("match_number") or 0))
        return by_team

    def recent_hard_wins(self, team, completed_by_team):
        hard = 0
        for row in reversed(completed_by_team.get(team, [])):
            if row.get("actual_advancing_team") != team:
                break
            if self.is_hard_win(row, team):
                hard += 1
                continue
            break
        return hard

    def is_hard_win(self, row, team):
        probability = self.actual_advance_probability(row, team)
        margin = self.margin(row)
        if self.was_penalty_advancement(row):
            return True
        if probability is not None and probability >= 0.65 and margin is not None and margin <= 1:
            return True
        return False

    def actual_advance_probability(self, row, team):
        if team == row.get("team1"):
            return self.float_value(row.get("team1_advance_probability"))
        if team == row.get("team2"):
            return self.float_value(row.get("team2_advance_probability"))
        return None

    def margin(self, row):
        score1 = self.score_value(row.get("team1_score_final"), row.get("team1_score_90"))
        score2 = self.score_value(row.get("team2_score_final"), row.get("team2_score_90"))
        if score1 is None or score2 is None:
            return None
        return abs(score1 - score2)

    def score(self, row):
        score1 = self.score_value(row.get("team1_score_final"), row.get("team1_score_90"))
        score2 = self.score_value(row.get("team2_score_final"), row.get("team2_score_90"))
        if score1 is None or score2 is None:
            return ""
        return f"{score1}-{score2}"

    def score_value(self, final_score, regulation_score):
        value = final_score if final_score not in (None, "") else regulation_score
        return self.int_value(value)

    def was_penalty_advancement(self, row):
        score1 = self.score_value(row.get("team1_score_final"), row.get("team1_score_90"))
        score2 = self.score_value(row.get("team2_score_final"), row.get("team2_score_90"))
        return score1 is not None and score2 is not None and score1 == score2

    def next_match_date(self, row):
        for key in ("date",):
            value = row.get(key, "")
            if value:
                match_number = self.int_value(row.get("match_number"))
                if match_number is None:
                    return ""
                if match_number <= 96:
                    return "2026-07-11"
                if match_number <= 100:
                    return "2026-07-15"
                if match_number <= 102:
                    return "2026-07-19"
        return ""

    def opponent(self, row, team):
        if row.get("team1") == team:
            return row.get("team2", "")
        if row.get("team2") == team:
            return row.get("team1", "")
        return ""

    def source_for_match(self, row):
        return row.get("source", "") or "match_intelligence_agent"

    def context_key(self, row):
        return (
            row.get("team", ""),
            row.get("reason", ""),
            row.get("active_from", ""),
            row.get("active_until", ""),
        )

    def read_csv(self, path):
        if not os.path.exists(path):
            return []
        with open(path, newline="") as f:
            return list(csv.DictReader(f))

    def write_csv(self, path, fields, rows):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows([
                {field: row.get(field, "") for field in fields}
                for row in rows
            ])

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

    def cap(self, value, lower, upper):
        return max(lower, min(upper, int(round(value))))

    def now(self):
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
