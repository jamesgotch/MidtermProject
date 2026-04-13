from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from pathlib import Path
from urllib import error, parse, request


ROOT_DIR = Path(__file__).resolve().parent
DATABASE_PATH = ROOT_DIR / "incidents.db"
CSV_PATH = ROOT_DIR / "incidents.csv"
ARCGIS_GEOCODER_URL = "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates"

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
    "latitude",
    "longitude",
    "geocode_provider",
    "geocoded_query",
    "geocode_status",
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
    "latitude": ["latitude", "Latitude"],
    "longitude": ["longitude", "Longitude"],
    "geocode_provider": ["geocode_provider", "Geocode Provider"],
    "geocoded_query": ["geocoded_query", "Geocoded Query"],
    "geocode_status": ["geocode_status", "Geocode Status"],
}

SCHEMA_COLUMNS = {
    "incident_key": "TEXT PRIMARY KEY",
    "record_id": "TEXT",
    "incident_date": "TEXT",
    "time": "TEXT",
    "division": "TEXT",
    "title": "TEXT",
    "location": "TEXT",
    "summary": "TEXT",
    "adults_arrested": "TEXT",
    "pd_contact_number": "TEXT",
    "source_url": "TEXT",
    "latitude": "REAL",
    "longitude": "REAL",
    "geocode_provider": "TEXT DEFAULT ''",
    "geocoded_query": "TEXT DEFAULT ''",
    "geocode_status": "TEXT DEFAULT 'pending'",
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
                source_url TEXT,
                latitude REAL,
                longitude REAL,
                geocode_provider TEXT DEFAULT '',
                geocoded_query TEXT DEFAULT '',
                geocode_status TEXT DEFAULT 'pending'
            )
            """
        )

        existing_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(incidents)").fetchall()
        }
        for column_name, column_definition in SCHEMA_COLUMNS.items():
            if column_name in existing_columns:
                continue

            connection.execute(f"ALTER TABLE incidents ADD COLUMN {column_name} {column_definition}")


def normalize_incident(raw_incident: dict[str, str]) -> dict[str, str | float | None]:
    incident: dict[str, str | float | None] = {field: "" for field in INCIDENT_FIELDS}
    incident["latitude"] = None
    incident["longitude"] = None
    incident["geocode_provider"] = ""
    incident["geocoded_query"] = ""
    incident["geocode_status"] = "pending"

    for field_name, possible_keys in FIELD_ALIASES.items():
        for key in possible_keys:
            value = raw_incident.get(key)
            if value is None:
                continue

            if field_name in {"latitude", "longitude"}:
                text_value = str(value).strip()
                if not text_value:
                    break

                try:
                    incident[field_name] = float(text_value)
                except ValueError:
                    incident[field_name] = None
                break

            cleaned_value = str(value).strip()
            if cleaned_value:
                incident[field_name] = cleaned_value
                break

    if not incident["location"]:
        incident["geocode_status"] = "missing"

    return incident


def make_incident_key(incident: dict[str, str | float | None]) -> str:
    record_id = str(incident.get("record_id", "")).strip()
    if record_id:
        return record_id

    payload = json.dumps(incident, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def deduplicate_incidents(incidents: list[dict[str, str]]) -> list[dict[str, str | float | None]]:
    unique_incidents: list[dict[str, str | float | None]] = []
    seen_keys: set[str] = set()

    for raw_incident in incidents:
        incident = normalize_incident(raw_incident)
        incident_key = make_incident_key(incident)
        if incident_key in seen_keys:
            continue

        seen_keys.add(incident_key)
        unique_incidents.append(incident)

    return unique_incidents


def read_incidents_from_csv(csv_path: Path = CSV_PATH) -> list[dict[str, str | float | None]]:
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


def merge_incident_lists(*incident_groups: list[dict[str, str]]) -> list[dict[str, str | float | None]]:
    merged_by_key: dict[str, dict[str, str | float | None]] = {}

    for incidents in incident_groups:
        for raw_incident in incidents:
            incident = normalize_incident(raw_incident)
            merged_by_key[make_incident_key(incident)] = incident

    return list(merged_by_key.values())


def build_geocode_query(location: str) -> str | None:
    raw_location = str(location or "").strip()
    if not raw_location:
        return None

    query = (
        raw_location.replace("@", " and ")
        .replace("/", " and ")
        .replace("\u2011", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
    )
    query = query.replace(" block of", "").replace(" Block of", "")
    query = query.replace(" Bl ", " Blvd ").replace(" Av ", " Ave ")
    query = query.replace(" Wy", " Way").replace(" Ct", " Court")
    query = " ".join(query.split())

    if not query:
        return None

    if "colorado springs" in query.lower() or query.lower().endswith(", co"):
        return query

    return f"{query}, Colorado Springs, CO"


def geocode_location(query: str) -> dict[str, str | float] | None:
    params = parse.urlencode(
        {
            "f": "pjson",
            "maxLocations": 1,
            "singleLine": query,
        }
    )
    url = f"{ARCGIS_GEOCODER_URL}?{params}"

    request_headers = {
        "Accept": "application/json",
        "User-Agent": "MidtermProject/1.0",
    }

    try:
        with request.urlopen(request.Request(url, headers=request_headers), timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (error.URLError, TimeoutError, json.JSONDecodeError):
        return None

    candidate = payload.get("candidates", [{}])[0]
    location = candidate.get("location") if isinstance(candidate, dict) else None
    if not location:
        return None

    return {
        "latitude": float(location["y"]),
        "longitude": float(location["x"]),
        "geocode_provider": "ArcGIS",
        "geocoded_query": candidate.get("address") or query,
    }


def geocode_missing_incidents(incident_keys: set[str] | None = None) -> int:
    create_table()

    query = (
        "SELECT incident_key, location FROM incidents "
        "WHERE (geocode_status IS NULL OR geocode_status = '' OR geocode_status = 'pending')"
    )
    parameters: list[str] = []

    if incident_keys:
        placeholders = ", ".join("?" for _ in incident_keys)
        query += f" AND incident_key IN ({placeholders})"
        parameters.extend(sorted(incident_keys))

    with get_connection() as connection:
        rows = connection.execute(query, parameters).fetchall()
        geocoded_count = 0

        for row in rows:
            location = str(row["location"] or "").strip()
            if not location:
                connection.execute(
                    "UPDATE incidents SET geocode_status = 'missing' WHERE incident_key = ?",
                    (row["incident_key"],),
                )
                continue

            geocode_query = build_geocode_query(location)
            if not geocode_query:
                connection.execute(
                    "UPDATE incidents SET geocode_status = 'missing' WHERE incident_key = ?",
                    (row["incident_key"],),
                )
                continue

            geocoded = geocode_location(geocode_query)
            if not geocoded:
                connection.execute(
                    """
                    UPDATE incidents
                    SET geocode_status = 'unresolved',
                        geocoded_query = ?
                    WHERE incident_key = ?
                    """,
                    (geocode_query, row["incident_key"]),
                )
                continue

            connection.execute(
                """
                UPDATE incidents
                SET latitude = ?,
                    longitude = ?,
                    geocode_provider = ?,
                    geocoded_query = ?,
                    geocode_status = 'resolved'
                WHERE incident_key = ?
                """,
                (
                    geocoded["latitude"],
                    geocoded["longitude"],
                    geocoded["geocode_provider"],
                    geocoded["geocoded_query"],
                    row["incident_key"],
                ),
            )
            geocoded_count += 1

    return geocoded_count


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
                source_url,
                latitude,
                longitude,
                geocode_provider,
                geocoded_query,
                geocode_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    incident.get("latitude"),
                    incident.get("longitude"),
                    incident.get("geocode_provider", ""),
                    incident.get("geocoded_query", ""),
                    "pending" if incident.get("location") else "missing",
                )
                for incident in clean_incidents
            ],
        )

    geocode_missing_incidents()
    return len(clean_incidents)


def upsert_incidents(incidents: list[dict[str, str]]) -> tuple[int, int]:
    create_table()
    clean_incidents = deduplicate_incidents(incidents)
    incident_keys = {make_incident_key(incident) for incident in clean_incidents}

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
                source_url,
                latitude,
                longitude,
                geocode_provider,
                geocoded_query,
                geocode_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                source_url = excluded.source_url,
                latitude = CASE WHEN incidents.location IS excluded.location THEN incidents.latitude ELSE NULL END,
                longitude = CASE WHEN incidents.location IS excluded.location THEN incidents.longitude ELSE NULL END,
                geocode_provider = CASE WHEN incidents.location IS excluded.location THEN incidents.geocode_provider ELSE '' END,
                geocoded_query = CASE WHEN incidents.location IS excluded.location THEN incidents.geocoded_query ELSE '' END,
                geocode_status = CASE
                    WHEN excluded.location = '' THEN 'missing'
                    WHEN incidents.location IS excluded.location THEN incidents.geocode_status
                    ELSE 'pending'
                END
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
                    None,
                    None,
                    "",
                    "",
                    "pending" if incident.get("location") else "missing",
                )
                for incident in clean_incidents
            ],
        )

    geocoded_count = geocode_missing_incidents(incident_keys)
    return count_incidents(), geocoded_count


def load_incidents() -> list[dict[str, str | float | None]]:
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
                source_url,
                latitude,
                longitude,
                geocode_provider,
                geocoded_query,
                geocode_status
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
    if count_incidents() == 0:
        csv_incidents = read_incidents_from_csv()
        if csv_incidents:
            replace_all_incidents(csv_incidents)
            return

    geocode_missing_incidents()