from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

from sqlmodel import Session, select


PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
	sys.path.insert(0, str(PROJECT_ROOT))

from incidents_init import DEFAULT_BLOTTER_URL, scrape_all_incidents, write_data_csv  # noqa: E402
from incidents_instances import generate_incident_instances  # noqa: E402
from models import Incident, engine  # noqa: E402


CSV_PATH = PROJECT_ROOT / "incidents.csv"


def read_existing_csv_rows(csv_path: Path) -> list[dict[str, str]]:
	if not csv_path.exists():
		return []

	with csv_path.open("r", encoding="utf-8", newline="") as csv_file:
		return [dict(row) for row in csv.DictReader(csv_file)]


def make_incident_key(row: dict[str, str]) -> str:
	record_id = (row.get("Record ID") or row.get("record_id") or "").strip()
	if record_id:
		return record_id

	payload = json.dumps(row, sort_keys=True, ensure_ascii=True)
	return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def to_csv_row(row: dict[str, str]) -> dict[str, str]:
	return {
		"Record ID": row.get("record_id", ""),
		"Incident Date": row.get("incident_date", ""),
		"Time": row.get("time", ""),
		"Division": row.get("division", ""),
		"Title": row.get("title", ""),
		"Location": row.get("location", ""),
		"Summary": row.get("summary", ""),
		"Adults Arrested": row.get("adults_arrested", ""),
		"PD Contact & Number": row.get("pd_contact_number", ""),
	}


def update_incident_database(csv_path: Path) -> int:
	incidents = generate_incident_instances(csv_path=str(csv_path))

	with Session(engine) as session:
		existing_keys = set(session.exec(select(Incident.incident_key)).all())
		new_incidents = [incident for incident in incidents if incident.incident_key not in existing_keys]
		session.add_all(new_incidents)
		session.commit()

	return len(new_incidents)


def main() -> None:
	existing_rows = read_existing_csv_rows(CSV_PATH)
	existing_keys = {make_incident_key(row) for row in existing_rows}

	scraped_rows = scrape_all_incidents(start_url=DEFAULT_BLOTTER_URL)
	scraped_csv_rows = [to_csv_row(row) for row in scraped_rows]
	scraped_keys = {make_incident_key(row) for row in scraped_csv_rows}

	new_keys = [key for key in scraped_keys if key not in existing_keys]

	write_data_csv(scraped_rows, csv_path=str(CSV_PATH))
	inserted_count = update_incident_database(CSV_PATH)

	print(f"Existing incidents before update: {len(existing_rows)}")
	print(f"Current incidents after scrape: {len(scraped_csv_rows)}")
	print(f"New incidents found: {len(new_keys)}")
	print(f"New incidents inserted into database: {inserted_count}")


if __name__ == "__main__":
	main()
