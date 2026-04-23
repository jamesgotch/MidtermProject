from __future__ import annotations

import argparse
from collections import Counter

from database import ensure_starting_data, load_incidents


def count_by_field(field_name: str, area: str) -> list[tuple[str, int]]:
    ensure_starting_data(area=area)
    incidents = load_incidents(area=area)

    counter = Counter()
    for incident in incidents:
        value = (incident.get(field_name) or "").strip()
        if value:
            counter[value] += 1

    return counter.most_common()


def print_query_results(area: str) -> None:
    type_counts = count_by_field("title", area)
    division_counts = count_by_field("division", area)

    print("Top Incident Types")
    for title, count in type_counts[:15]:
        print(f"{count:>5} | {title}")

    print("\nTop Divisions")
    for division, count in division_counts[:15]:
        print(f"{count:>5} | {division}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Read and summarize database statistics.")
    parser.add_argument("--area", default="colorado_springs", help="Area to read from")
    args = parser.parse_args()

    print_query_results(args.area)
