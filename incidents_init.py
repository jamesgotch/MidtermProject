from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
import subprocess
import sys
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright
from sqlmodel import Session, select

from incidents_instances import generate_incident_instances
from models import Incident, engine


DEFAULT_BLOTTER_URL = "https://web2.coloradosprings.gov/policeblotter/"
DEFAULT_CSV_PATH = "incidents.csv"
PAGE_LOAD_TIMEOUT_MS = 60000
PAGE_STABILIZE_DELAY_MS = 250
PAGINATION_POLL_ATTEMPTS = 80
OUTPUT_COLUMNS = [
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


def _normalize_header(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def _extract_incident_blocks(soup: BeautifulSoup) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    for container in soup.select("td.col-justify-start"):
        row_data: dict[str, str] = {}

        for block in container.select("div.row"):
            label_node = block.find("label")
            value_node = block.select_one("div.col-9")
            if not label_node or not value_node:
                continue

            key = _normalize_header(label_node.get_text(" ", strip=True))
            row_data[key] = value_node.get_text(" ", strip=True)

        if row_data and ("record_id" in row_data or "incident_date" in row_data or "title" in row_data):
            rows.append(row_data)

    return rows


def _dedupe_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    deduped: list[dict[str, str]] = []
    seen_signatures: set[str] = set()

    for row in rows:
        record_id = (row.get("record_id") or "").strip()
        signature = record_id or json.dumps(row, sort_keys=True, ensure_ascii=True)
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        deduped.append(row)

    return deduped


def _first_record_id(rows: list[dict[str, str]]) -> str:
    if not rows:
        return ""
    return (rows[0].get("record_id") or "").strip()


def _ensure_playwright_browser() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Unable to install the Chromium browser required for scraping. "
            f"playwright install stderr: {result.stderr.strip() or result.stdout.strip()}"
        )


async def _scrape_all_incidents_async(start_url: str, delay_seconds: float) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    page_number = 1
    seen_page_signatures: set[tuple[str, ...]] = set()

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(start_url, wait_until="networkidle", timeout=PAGE_LOAD_TIMEOUT_MS)

        while True:
            soup = BeautifulSoup(await page.content(), "html.parser")
            page_rows = _extract_incident_blocks(soup)
            if not page_rows:
                await browser.close()
                raise RuntimeError(f"No incidents were found on page {page_number}.")

            page_signature = tuple(
                (row.get("record_id") or json.dumps(row, sort_keys=True, ensure_ascii=True))
                for row in page_rows
            )
            if page_signature in seen_page_signatures:
                break
            seen_page_signatures.add(page_signature)

            for row in page_rows:
                row["source_url"] = f"{page.url}#page={page_number}"
            rows.extend(page_rows)

            next_button = page.locator("button.go-next")
            if await next_button.count() == 0 or await next_button.is_disabled():
                break

            current_first_id = _first_record_id(page_rows)
            await next_button.click()

            advanced = False
            for _ in range(PAGINATION_POLL_ATTEMPTS):
                await page.wait_for_timeout(PAGE_STABILIZE_DELAY_MS)
                next_rows = _extract_incident_blocks(BeautifulSoup(await page.content(), "html.parser"))
                next_first_id = _first_record_id(next_rows)
                if next_rows and next_first_id != current_first_id:
                    advanced = True
                    break

            if not advanced:
                await browser.close()
                raise RuntimeError(f"Pagination did not advance after page {page_number}.")

            page_number += 1
            if delay_seconds > 0:
                await page.wait_for_timeout(int(delay_seconds * 1000))

        await browser.close()

    return _dedupe_rows(rows)


def scrape_all_incidents(start_url: str = DEFAULT_BLOTTER_URL, delay_seconds: float = 0.2) -> list[dict[str, str]]:
    try:
        return asyncio.run(_scrape_all_incidents_async(start_url=start_url, delay_seconds=delay_seconds))
    except PlaywrightTimeoutError as error:
        raise RuntimeError(f"Timed out while scraping {start_url}: {error}") from error
    except PlaywrightError as error:
        if "Executable doesn't exist" not in str(error):
            raise

    _ensure_playwright_browser()
    return asyncio.run(_scrape_all_incidents_async(start_url=start_url, delay_seconds=delay_seconds))


def write_data_csv(rows: list[dict[str, str]], csv_path: str = DEFAULT_CSV_PATH) -> str:
    if not rows:
        raise ValueError("No incident rows were scraped from the source site.")

    headers = [label for _, label in OUTPUT_COLUMNS]
    path = Path(csv_path)

    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({label: row.get(key, "") for key, label in OUTPUT_COLUMNS})

    return str(path)


def scrape_and_save_data(
    csv_path: str = DEFAULT_CSV_PATH,
    start_url: str = DEFAULT_BLOTTER_URL,
    delay_seconds: float = 0.2,
) -> tuple[str, int]:
    rows = scrape_all_incidents(start_url=start_url, delay_seconds=delay_seconds)
    output_path = write_data_csv(rows, csv_path=csv_path)
    return output_path, len(rows)


def initialize_incident_database(
    csv_path: str = DEFAULT_CSV_PATH,
    scrape_first: bool = True,
    start_url: str = DEFAULT_BLOTTER_URL,
) -> tuple[int, int]:
    """Populate incidents.db from scraped or existing CSV data."""
    scraped_count = 0
    if scrape_first:
        _, scraped_count = scrape_and_save_data(csv_path=csv_path, start_url=start_url)

    incidents = generate_incident_instances(csv_path=csv_path)

    with Session(engine) as session:
        existing_keys = set(session.exec(select(Incident.incident_key)).all())
        new_incidents = [incident for incident in incidents if incident.incident_key not in existing_keys]
        session.add_all(new_incidents)
        session.commit()

    inserted_count = len(new_incidents)

    return scraped_count, inserted_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize incidents.db from Colorado Springs blotter data.")
    parser.add_argument("--csv", default=DEFAULT_CSV_PATH, help="Path to incidents CSV file")
    parser.add_argument(
        "--start-url",
        default=DEFAULT_BLOTTER_URL,
        help="Starting URL for police blotter scraping",
    )
    parser.add_argument(
        "--skip-scrape",
        action="store_true",
        help="Use existing CSV file and do not scrape before loading",
    )
    args = parser.parse_args()

    scraped_count, inserted_count = initialize_incident_database(
        csv_path=args.csv,
        scrape_first=not args.skip_scrape,
        start_url=args.start_url,
    )

    if args.skip_scrape:
        print(f"Inserted {inserted_count} incident rows into incidents.db from existing CSV")
    else:
        print(f"Scraped {scraped_count} rows to {args.csv}")
        print(f"Inserted {inserted_count} incident rows into incidents.db")


if __name__ == "__main__":
    main()