from __future__ import annotations

import argparse

from scraper import DEFAULT_BLOTTER_URL, refresh_data


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape the police blotter and refresh the local data files.")
    parser.add_argument(
        "--url",
        default=DEFAULT_BLOTTER_URL,
        help="Blotter page to scrape",
    )
    args = parser.parse_args()

    summary = refresh_data(start_url=args.url)

    print(f"Previous incidents: {summary['previous_count']}")
    print(f"Current incidents: {summary['current_count']}")
    print(f"New incidents: {summary['new_count']}")
    print("Saved incidents.csv and incidents.db")


if __name__ == "__main__":
    main()
