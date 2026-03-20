from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from models import Incident


DEFAULT_CSV_PATH = "incidents.csv"


def read_csv_rows(csv_path: str) -> list[dict[str, str]]:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"{csv_path} not found.")

    with path.open(mode="r", encoding="utf-8", newline="") as file:
        return [dict(row) for row in csv.DictReader(file)]


def _pick_first(row: dict[str, str], keys: list[str]) -> str:
    for key in keys:
        value = (row.get(key) or "").strip()
        if value:
            return value
    return ""


def _row_signature(row: dict[str, str]) -> str:
    payload = json.dumps(row, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def generate_incident_instances(
    csv_path: str = DEFAULT_CSV_PATH,
) -> list[Incident]:
    """Read the incidents CSV file and return a list of Incident objects."""
    rows = read_csv_rows(csv_path)
    incidents: list[Incident] = []

    for row in rows:
        record_id = _pick_first(row, ["record_id", "Record ID"])
        incident_key = record_id or _pick_first(
            row,
            ["case_number", "case", "report_number", "incident_number", "event_number"],
        )
        if not incident_key:
            incident_key = _row_signature(row)

        incidents.append(
            Incident(
                incident_key=incident_key,
                record_id=record_id or None,
                incident_date=_pick_first(row, ["incident_date", "Incident Date", "date", "report_date"]),
                time=_pick_first(row, ["time", "Time"]),
                division=_pick_first(row, ["division", "Division"]),
                title=_pick_first(row, ["title", "Title", "incident_type", "offense", "nature"]),
                location=_pick_first(row, ["location", "Location", "address", "block", "street"]),
                summary=_pick_first(row, ["summary", "Summary", "description"]),
                adults_arrested=_pick_first(row, ["adults_arrested", "Adults Arrested"]),
                pd_contact_number=_pick_first(row, ["pd_contact_number", "PD Contact & Number"]),
                source_url=_pick_first(row, ["source_url", "Source URL"]),
                raw_data=json.dumps(row, ensure_ascii=True, sort_keys=True),
            )
        )

    return incidents


def get_incident_instances(csv_path: str) -> list[Incident]:
    """Backward-compatible alias."""
    return generate_incident_instances(csv_path=csv_path)
