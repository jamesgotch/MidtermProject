from __future__ import annotations

import argparse

from colorado_springs.scraper import DEFAULT_BLOTTER_URL, refresh_data


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape the police blotter and refresh the local data files.")
    parser.add_argument(
        "--url",
        default=DEFAULT_BLOTTER_URL,
        help="Blotter page to scrape",
    )
    parser.add_argument(
        "--area",
        default="colorado_springs",
        help="Area to update (folder name)",
    )
    args = parser.parse_args()

    if args.area == "colorado_springs":
        from colorado_springs.scraper import refresh_data
        summary = refresh_data(start_url=args.url)
    else:
        import importlib
        try:
            scraper_module = importlib.import_module(f"{args.area}.scraper")
            summary = scraper_module.refresh_data(start_url=args.url)
        except ImportError:
            print(f"Error: Could not find scraper for area '{args.area}'")
            return

    print(f"Previous incidents: {summary['previous_count']}")
    print(f"Current incidents: {summary['current_count']}")
    print(f"New incidents: {summary['new_count']}")
    print(f"Geocoded incidents this run: {summary['geocoded_count']}")
    print(f"Saved {args.area}/incidents.csv and {args.area}/incidents.db")


if __name__ == "__main__":
    main()
