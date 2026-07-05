import csv
import json
import os
import shutil
from datetime import datetime, timezone


DEFAULT_SNAPSHOT_FILES = [
    "data/pre_tournament_ratings.json",
    "data/world_cup_2026_teams.csv",
    "data/world_cup_history.csv",
    "data/knockout_bracket.csv",
    "data/team_context_adjustments.csv",
    "data/player_scores.csv",
    "data/player_score_refresh_log.csv",
    "data/fifa_power_rankings.csv",
    "data/fifa_power_ranking_refresh_log.csv",
    "data/team_form_adjustments.csv",
    "data/team_player_strength.csv",
    "data/team_power_rankings.csv",
    "data/match_predictions.csv",
    "data/round_of_32_predictions.csv",
    "data/knockout_bracket_predictions.csv",
    "data/prediction_evaluation.csv",
    "data/team_ratings.json",
]


class RunHistoryRecorder:
    """Stores point-in-time model inputs and outputs for reproducibility."""

    def __init__(
        self,
        history_dir="data/run_history",
        index_csv="data/run_history/index.csv",
        snapshot_files=None,
    ):
        self.history_dir = history_dir
        self.index_csv = index_csv
        self.snapshot_files = snapshot_files or DEFAULT_SNAPSHOT_FILES

    def record(self, run_type, summary=None):
        os.makedirs(self.history_dir, exist_ok=True)
        timestamp = self.now()
        run_id = timestamp.replace(":", "").replace("-", "").replace("+", "Z")
        run_dir = os.path.join(self.history_dir, run_id)
        os.makedirs(run_dir, exist_ok=True)

        copied_files = []
        missing_files = []
        for source in self.snapshot_files:
            if not os.path.exists(source):
                missing_files.append(source)
                continue

            destination = os.path.join(run_dir, source)
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            shutil.copy2(source, destination)
            copied_files.append(source)

        champion = self.projected_champion()
        manifest = {
            "run_id": run_id,
            "timestamp": timestamp,
            "run_type": run_type,
            "summary": summary or {},
            "projected_champion": champion,
            "copied_files": copied_files,
            "missing_files": missing_files,
        }
        manifest_path = os.path.join(run_dir, "manifest.json")
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=4)

        self.append_index(manifest)
        return manifest

    def record_if_needed(self, run_type, summary=None):
        """
        Avoids noisy history during frequent live checks.

        A snapshot is stored when a result/news update changed model inputs.
        If nothing changed, one daily checkpoint is stored at most.
        """
        summary = summary or {}
        if self.has_meaningful_update(summary):
            return self.record(run_type, summary)
        if not self.has_snapshot_today():
            daily_summary = dict(summary)
            daily_summary["snapshot_reason"] = "daily_checkpoint"
            return self.record("daily_checkpoint", daily_summary)
        return None

    def has_meaningful_update(self, summary):
        return (
            int(summary.get("power_ranking_updates", 0) or 0) > 0
            or int(summary.get("player_score_updates", 0) or 0) > 0
            or int(summary.get("match_result_updates", 0) or 0) > 0
            or int(summary.get("strength_adjustments_applied", 0) or 0) > 0
            or int(summary.get("news_adjustments_applied", 0) or 0) > 0
        )

    def has_snapshot_today(self):
        if not os.path.exists(self.index_csv):
            return False

        today = datetime.now(timezone.utc).date().isoformat()
        with open(self.index_csv, newline="") as f:
            for row in csv.DictReader(f):
                timestamp = row.get("timestamp", "")
                if timestamp.startswith(today):
                    return True
        return False

    def projected_champion(self, predictions_csv="data/knockout_bracket_predictions.csv"):
        if not os.path.exists(predictions_csv):
            return ""

        with open(predictions_csv, newline="") as f:
            for row in csv.DictReader(f):
                if row.get("round") == "Final":
                    return row.get("projected_advancing_team", "")
        return ""

    def append_index(self, manifest):
        os.makedirs(os.path.dirname(self.index_csv), exist_ok=True)
        fields = [
            "run_id",
            "timestamp",
            "run_type",
            "projected_champion",
            "match_result_updates",
            "power_ranking_updates",
            "player_score_updates",
            "strength_adjustments_applied",
            "news_adjustments_applied",
            "snapshot_reason",
            "snapshot_path",
        ]
        exists = os.path.exists(self.index_csv)
        if exists:
            self.migrate_index_schema(fields)

        with open(self.index_csv, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            if not exists:
                writer.writeheader()
            summary = manifest.get("summary", {})
            writer.writerow({
                "run_id": manifest["run_id"],
                "timestamp": manifest["timestamp"],
                "run_type": manifest["run_type"],
                "projected_champion": manifest.get("projected_champion", ""),
                "match_result_updates": summary.get("match_result_updates", ""),
                "power_ranking_updates": summary.get("power_ranking_updates", ""),
                "player_score_updates": summary.get("player_score_updates", ""),
                "strength_adjustments_applied": summary.get("strength_adjustments_applied", ""),
                "news_adjustments_applied": summary.get("news_adjustments_applied", ""),
                "snapshot_reason": summary.get("snapshot_reason", "meaningful_update"),
                "snapshot_path": os.path.join(self.history_dir, manifest["run_id"]),
            })

    def migrate_index_schema(self, fields):
        with open(self.index_csv, newline="") as f:
            reader = csv.DictReader(f)
            existing_fields = reader.fieldnames or []
            if existing_fields == fields:
                return
            rows = list(reader)

        with open(self.index_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                clean_row = {field: row.get(field, "") for field in fields}
                if not clean_row["snapshot_reason"]:
                    clean_row["snapshot_reason"] = "legacy_snapshot"
                writer.writerow(clean_row)

    def now(self):
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
