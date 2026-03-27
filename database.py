from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
DATABASE_PATH = ROOT_DIR / "incidents.db"
CSV_PATH = ROOT_DIR / "incidents.csv"

INCIDENT_FIELDS = [
    "record_id",
    "incident_date",
    "time",
    "division",
    "title",
    "location",
    "summary",
    "adults_arrested",
    "pd_contact_number",
    "source_url",
]

CSV_COLUMNS = [
    ("record_id", "Record ID"),
    ("incident_date", "Incident Date"),
    ("time", "Time"),
    ("division", "Division"),
    ("title", "Title"),
    ("location", "Location"),
    ("summary", "Summary"),
    ("adults_arrested", "Adults Arrested"),
    ("pd_contact_number", "PD Contact & Number"),
]

FIELD_ALIASES = {
    "record_id": ["record_id", "Record ID"],
    "incident_date": ["incident_date", "Incident Date"],
    "time": ["time", "Time"],
    "division": ["division", "Division"],
    "title": ["title", "Title"],
    "location": ["location", "Location"],
    "summary": ["summary", "Summary"],
    "adults_arrested": ["adults_arrested", "Adults Arrested"],
    "pd_contact_number": ["pd_contact_number", "PD Contact & Number"],
    "source_url": ["source_url", "Source URL"],
}


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def create_table() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS incidents (
                incident_key TEXT PRIMARY KEY,
                record_id TEXT,
                incident_date TEXT,
                time TEXT,
                division TEXT,
                title TEXT,
                location TEXT,
                summary TEXT,
                adults_arrested TEXT,
                pd_contact_number TEXT,
                source_url TEXT
            )
            """
        )


def normalize_incident(raw_incident: dict[str, str]) -> dict[str, str]:
    incident = {field: "" for field in INCIDENT_FIELDS}

    for field_name, possible_keys in FIELD_ALIASES.items():
        for key in possible_keys:
            value = raw_incident.get(key)
            if value is None:
                continue

            cleaned_value = str(value).strip()
            if cleaned_value:
                incident[field_name] = cleaned_value
                break

    return incident


def make_incident_key(incident: dict[str, str]) -> str:
    record_id = incident.get("record_id", "").strip()
    if record_id:
        return record_id

    payload = json.dumps(incident, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def deduplicate_incidents(incidents: list[dict[str, str]]) -> list[dict[str, str]]:
    unique_incidents: list[dict[str, str]] = []
    seen_keys: set[str] = set()

    for raw_incident in incidents:
        incident = normalize_incident(raw_incident)
        incident_key = make_incident_key(incident)
        if incident_key in seen_keys:
            continue

        seen_keys.add(incident_key)
        unique_incidents.append(incident)

    return unique_incidents


def read_incidents_from_csv(csv_path: Path = CSV_PATH) -> list[dict[str, str]]:
    if not csv_path.exists():
        return []

    with csv_path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        return [normalize_incident(dict(row)) for row in reader]


def write_incidents_to_csv(incidents: list[dict[str, str]], csv_path: Path = CSV_PATH) -> None:
    clean_incidents = deduplicate_incidents(incidents)

    with csv_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=[column_name for _, column_name in CSV_COLUMNS])
        writer.writeheader()

        for incident in clean_incidents:
            writer.writerow({column_name: incident.get(field_name, "") for field_name, column_name in CSV_COLUMNS})


def merge_incident_lists(*incident_groups: list[dict[str, str]]) -> list[dict[str, str]]:
    merged_by_key: dict[str, dict[str, str]] = {}

    for incidents in incident_groups:
        for raw_incident in incidents:
            incident = normalize_incident(raw_incident)
            merged_by_key[make_incident_key(incident)] = incident

    return list(merged_by_key.values())


def replace_all_incidents(incidents: list[dict[str, str]]) -> int:
    create_table()
    clean_incidents = deduplicate_incidents(incidents)

    with get_connection() as connection:
        connection.execute("DELETE FROM incidents")
        connection.executemany(
            """
            INSERT INTO incidents (
                incident_key,
                record_id,
                incident_date,
                time,
                division,
                title,
                location,
                summary,
                adults_arrested,
                pd_contact_number,
                source_url
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    make_incident_key(incident),
                    incident["record_id"],
                    incident["incident_date"],
                    incident["time"],
                    incident["division"],
                    incident["title"],
                    incident["location"],
                    incident["summary"],
                    incident["adults_arrested"],
                    incident["pd_contact_number"],
                    incident["source_url"],
                )
                for incident in clean_incidents
            ],
        )

    return len(clean_incidents)


def upsert_incidents(incidents: list[dict[str, str]]) -> int:
    create_table()
    clean_incidents = deduplicate_incidents(incidents)

    with get_connection() as connection:
        connection.executemany(
            """
            INSERT INTO incidents (
                incident_key,
                record_id,
                incident_date,
                time,
                division,
                title,
                location,
                summary,
                adults_arrested,
                pd_contact_number,
                source_url
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(incident_key) DO UPDATE SET
                record_id = excluded.record_id,
                incident_date = excluded.incident_date,
                time = excluded.time,
                division = excluded.division,
                title = excluded.title,
                location = excluded.location,
                summary = excluded.summary,
                adults_arrested = excluded.adults_arrested,
                pd_contact_number = excluded.pd_contact_number,
                source_url = excluded.source_url
            """,
            [
                (
                    make_incident_key(incident),
                    incident["record_id"],
                    incident["incident_date"],
                    incident["time"],
                    incident["division"],
                    incident["title"],
                    incident["location"],
                    incident["summary"],
                    incident["adults_arrested"],
                    incident["pd_contact_number"],
                    incident["source_url"],
                )
                for incident in clean_incidents
            ],
        )

    return count_incidents()


def load_incidents() -> list[dict[str, str]]:
    create_table()

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                record_id,
                incident_date,
                time,
                division,
                title,
                location,
                summary,
                adults_arrested,
                pd_contact_number,
                source_url
            FROM incidents
            """
        ).fetchall()

    return [dict(row) for row in rows]


def count_incidents() -> int:
    create_table()

    with get_connection() as connection:
        row = connection.execute("SELECT COUNT(*) FROM incidents").fetchone()

    return int(row[0]) if row else 0


def ensure_starting_data() -> None:
    create_table()
    if count_incidents() > 0:
        return

    csv_incidents = read_incidents_from_csv()
    if csv_incidents:
        replace_all_incidents(csv_incidents)