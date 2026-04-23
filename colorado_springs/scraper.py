from __future__ import annotations

import asyncio
import json
import re
import subprocess
import sys

from bs4 import BeautifulSoup
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from database import (
    deduplicate_incidents,
    load_incidents,
    make_incident_key,
    merge_incident_lists,
    upsert_incidents,
    write_incidents_to_csv,
)


DEFAULT_BLOTTER_URL = "https://web2.coloradosprings.gov/policeblotter/"
PAGE_LOAD_TIMEOUT_MS = 60000
PAGE_STABILIZE_DELAY_MS = 250
PAGINATION_POLL_ATTEMPTS = 80


def normalize_label(label: str) -> str:
    text = label.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def extract_incidents_from_html(html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    incidents: list[dict[str, str]] = []

    for container in soup.select("td.col-justify-start"):
        incident: dict[str, str] = {}

        for row in container.select("div.row"):
            label = row.find("label")
            value = row.select_one("div.col-9")
            if not label or not value:
                continue

            incident[normalize_label(label.get_text(" ", strip=True))] = value.get_text(" ", strip=True)

        if incident:
            incidents.append(incident)

    return incidents


def first_record_id(incidents: list[dict[str, str]]) -> str:
    if not incidents:
        return ""
    return (incidents[0].get("record_id") or "").strip()


def ensure_playwright_browser() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Playwright could not install Chromium automatically. "
            f"Details: {result.stderr.strip() or result.stdout.strip()}"
        )


async def scrape_all_incidents_async(start_url: str, delay_seconds: float) -> list[dict[str, str]]:
    all_incidents: list[dict[str, str]] = []
    seen_pages: set[tuple[str, ...]] = set()
    page_number = 1

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(start_url, wait_until="networkidle", timeout=PAGE_LOAD_TIMEOUT_MS)

        while True:
            page_incidents = extract_incidents_from_html(await page.content())
            if not page_incidents:
                await browser.close()
                raise RuntimeError(f"No incidents were found on page {page_number}.")

            page_signature = tuple(
                (incident.get("record_id") or json.dumps(incident, sort_keys=True, ensure_ascii=True))
                for incident in page_incidents
            )
            if page_signature in seen_pages:
                break
            seen_pages.add(page_signature)

            for incident in page_incidents:
                incident["source_url"] = f"{page.url}#page={page_number}"

            all_incidents.extend(page_incidents)

            next_button = page.locator("button.go-next")
            if await next_button.count() == 0 or await next_button.is_disabled():
                break

            current_first_id = first_record_id(page_incidents)
            await next_button.click()

            page_changed = False
            for _ in range(PAGINATION_POLL_ATTEMPTS):
                await page.wait_for_timeout(PAGE_STABILIZE_DELAY_MS)
                next_page_incidents = extract_incidents_from_html(await page.content())
                if next_page_incidents and first_record_id(next_page_incidents) != current_first_id:
                    page_changed = True
                    break

            if not page_changed:
                await browser.close()
                raise RuntimeError(f"Pagination did not advance after page {page_number}.")

            page_number += 1
            if delay_seconds > 0:
                await page.wait_for_timeout(int(delay_seconds * 1000))

        await browser.close()

    return deduplicate_incidents(all_incidents)


def scrape_all_incidents(start_url: str = DEFAULT_BLOTTER_URL, delay_seconds: float = 0.2) -> list[dict[str, str]]:
    try:
        return asyncio.run(scrape_all_incidents_async(start_url=start_url, delay_seconds=delay_seconds))
    except PlaywrightTimeoutError as error:
        raise RuntimeError(f"Timed out while scraping {start_url}: {error}") from error
    except PlaywrightError as error:
        if "Executable doesn't exist" not in str(error):
            raise RuntimeError(f"Playwright failed while scraping {start_url}: {error}") from error

    ensure_playwright_browser()
    return asyncio.run(scrape_all_incidents_async(start_url=start_url, delay_seconds=delay_seconds))


def refresh_data(start_url: str = DEFAULT_BLOTTER_URL, delay_seconds: float = 0.2) -> dict[str, int]:
    area = "colorado_springs"
    previous_incidents = load_incidents(area=area)
    previous_keys = {make_incident_key(incident) for incident in previous_incidents}

    scraped_incidents = scrape_all_incidents(start_url=start_url, delay_seconds=delay_seconds)
    current_keys = {make_incident_key(incident) for incident in scraped_incidents}
    merged_incidents = merge_incident_lists(previous_incidents, scraped_incidents)

    write_incidents_to_csv(merged_incidents, area=area)
    saved_count, geocoded_count = upsert_incidents(scraped_incidents, area=area)

    return {
        "previous_count": len(previous_keys),
        "current_count": saved_count,
        "new_count": len(current_keys - previous_keys),
        "geocoded_count": geocoded_count,
    }