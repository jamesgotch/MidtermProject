from __future__ import annotations

import contextlib
import csv
import hashlib
import json
import typing
from pathlib import Path
from urllib import error, parse, request

from sqlalchemy import delete
from sqlmodel import Field, Session, SQLModel, create_engine, func, or_, select


ROOT_DIR = Path(__file__).resolve().parent
ARCGIS_GEOCODER_URL = "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates"


class Incident(SQLModel, table=True):
    __tablename__ = "incidents"

    # FIXED: Made incident_key optional with a default of None to satisfy Pydantic validation on updates
    incident_key: typing.Optional[str] = Field(default=None, primary_key=True)
    record_id: typing.Optional[str] = Field(default=None, index=True)
    incident_date: typing.Optional[str] = None
    time: typing.Optional[str] = None
    division: typing.Optional[str] = None
    title: typing.Optional[str] = None
    location: typing.Optional[str] = None
    summary: typing.Optional[str] = None
    adults_arrested: typing.Optional[str] = None
    pd_contact_number: typing.Optional[str] = None
    source_url: typing.Optional[str] = None
    latitude: typing.Optional[float] = None
    longitude: typing.Optional[float] = None
    geocode_provider: str = Field(default="")
    geocoded_query: str = Field(default="")
    geocode_status: str = Field(default="pending", index=True)


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

_engines: dict[str, typing.Any] = {}


def get_engine(area: str):
    global _engines
    if area not in _engines:
        db_path = get_db_path(area)
        db_url = f"sqlite:///{db_path}"
        _engines[area] = create_engine(db_url, connect_args={"check_same_thread": False})
    return _engines[area]

def get_db_path(area: str) -> Path:
    directory = ROOT_DIR / area
    directory.mkdir(parents=True, exist_ok=True)
    return directory / "incidents.db"

def get_csv_path(area: str) -> Path:
    directory = ROOT_DIR / area
    directory.mkdir(parents=True, exist_ok=True)
    return directory / "incidents.csv"


@contextlib.contextmanager
def get_session(area: str = "colorado_springs") -> typing.Iterator[Session]:
    engine = get_engine(area)
    with Session(engine) as session:
        yield session


def create_table(area: str = "colorado_springs") -> None:
    engine = get_engine(area)
    SQLModel.metadata.create_all(engine)


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


def read_incidents_from_csv(area: str = "colorado_springs") -> list[dict[str, str | float | None]]:
    csv_path = get_csv_path(area)
    if not csv_path.exists():
        return []

    with csv_path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        return [normalize_incident(dict(row)) for row in reader]


def write_incidents_to_csv(incidents: list[dict[str, str]], area: str = "colorado_springs") -> None:
    csv_path = get_csv_path(area)
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


def geocode_missing_incidents(incident_keys: set[str] | None = None, area: str = "colorado_springs") -> int:
    create_table(area)
    geocoded_count = 0
    with get_session(area) as session:
        statement = select(Incident).where(
            or_(Incident.geocode_status == "pending", Incident.geocode_status == "", Incident.geocode_status.is_(None))
        )
        if incident_keys:
            statement = statement.where(Incident.incident_key.in_(sorted(list(incident_keys))))

        incidents_to_geocode = session.exec(statement).all()

        for incident in incidents_to_geocode:
            location = str(incident.location or "").strip()
            if not location:
                incident.geocode_status = "missing"
                continue

            geocode_query = build_geocode_query(location)
            if not geocode_query:
                incident.geocode_status = "missing"
                continue

            geocoded = geocode_location(geocode_query)
            if not geocoded:
                incident.geocode_status = "unresolved"
                incident.geocoded_query = geocode_query
                continue

            incident.latitude = geocoded["latitude"]
            incident.longitude = geocoded["longitude"]
            incident.geocode_provider = geocoded["geocode_provider"]
            incident.geocoded_query = geocoded["geocoded_query"]
            incident.geocode_status = "resolved"
            geocoded_count += 1

        if incidents_to_geocode:
            session.commit()

    return geocoded_count


def replace_all_incidents(
    incidents: list[dict[str, str | float | None]], area: str = "colorado_springs"
) -> int:
    create_table(area)
    clean_incidents = deduplicate_incidents(incidents)

    with get_session(area) as session:
        session.exec(delete(Incident))
        session.commit()

        for inc_dict in clean_incidents:
            inc_dict["incident_key"] = make_incident_key(inc_dict)
            new_incident = Incident.model_validate(inc_dict)
            session.add(new_incident)

        session.commit()

    geocode_missing_incidents(area=area)
    return len(clean_incidents)


def upsert_incidents(
    incidents: list[dict[str, str | float | None]], area: str = "colorado_springs"
) -> tuple[int, int]:
    if not incidents:
        return count_incidents(area=area), 0

    create_table(area)
    clean_incidents = deduplicate_incidents(incidents)
    incident_keys_to_upsert = {make_incident_key(incident) for incident in clean_incidents}

    with get_session(area) as session:
        statement = select(Incident).where(Incident.incident_key.in_(list(incident_keys_to_upsert)))
        existing_incidents_map = {inc.incident_key: inc for inc in session.exec(statement).all()}

        for inc_dict in clean_incidents:
            key = make_incident_key(inc_dict)
            incident = existing_incidents_map.get(key)

            if incident:
                if incident.location == inc_dict["location"]:
                    inc_dict["latitude"] = incident.latitude
                    inc_dict["longitude"] = incident.longitude
                    inc_dict["geocode_provider"] = incident.geocode_provider
                    inc_dict["geocoded_query"] = incident.geocoded_query
                    inc_dict["geocode_status"] = incident.geocode_status
                else:
                    inc_dict["latitude"] = None
                    inc_dict["longitude"] = None
                    inc_dict["geocode_provider"] = ""
                    inc_dict["geocoded_query"] = ""
                    inc_dict["geocode_status"] = "pending" if inc_dict.get("location") else "missing"

                for k, v in inc_dict.items():
                    if hasattr(incident, k):
                        setattr(incident, k, v)
                session.add(incident)
            else:
                new_incident = Incident.model_validate(inc_dict)
                new_incident.incident_key = key
                session.add(new_incident)

        session.commit()

    geocoded_count = geocode_missing_incidents(incident_keys_to_upsert, area=area)
    return count_incidents(area=area), geocoded_count


def load_incidents(area: str = "colorado_springs") -> list[dict[str, str | float | None]]:
    create_table(area)
    with get_session(area) as session:
        incidents = session.exec(select(Incident)).all()
        return [inc.model_dump() for inc in incidents]


def count_incidents(area: str = "colorado_springs") -> int:
    create_table(area)
    with get_session(area) as session:
        count = session.exec(select(func.count()).select_from(Incident)).one_or_none()
    return count or 0


def ensure_starting_data(area: str = "colorado_springs") -> None:
    create_table(area)
    if count_incidents(area) == 0:
        csv_incidents = read_incidents_from_csv(area)
        if csv_incidents:
            replace_all_incidents(csv_incidents, area=area)
            return

    geocode_missing_incidents(area=area)
