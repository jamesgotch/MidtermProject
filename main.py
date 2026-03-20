from __future__ import annotations

import csv
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT_DIR = Path(__file__).resolve().parent
STATIC_DIR = ROOT_DIR / "static"
CSV_PATH = ROOT_DIR / "incidents.csv"
HOST = "127.0.0.1"
PORT = 8000


def load_incidents() -> list[dict[str, str]]:
    if not CSV_PATH.exists():
        return []

    with CSV_PATH.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        incidents = []
        for row in reader:
            incidents.append(
                {
                    "record_id": row.get("Record ID", ""),
                    "incident_date": row.get("Incident Date", ""),
                    "time": row.get("Time", ""),
                    "division": row.get("Division", ""),
                    "title": row.get("Title", ""),
                    "location": row.get("Location", ""),
                    "summary": row.get("Summary", ""),
                    "adults_arrested": row.get("Adults Arrested", ""),
                    "pd_contact_number": row.get("PD Contact & Number", ""),
                }
            )
    return incidents


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/api/incidents":
            incidents = load_incidents()
            payload = json.dumps({"incidents": incidents}, ensure_ascii=True).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        if parsed.path == "/":
            self.path = "/index.html"

        super().do_GET()


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), DashboardHandler)
    print(f"Dashboard running at http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()