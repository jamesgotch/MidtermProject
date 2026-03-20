from __future__ import annotations

from collections import Counter

from database import ensure_starting_data, load_incidents


def count_by_field(field_name: str) -> list[tuple[str, int]]:
    ensure_starting_data()
    incidents = load_incidents()

    counter = Counter()
    for incident in incidents:
        value = (incident.get(field_name) or "").strip()
        if value:
            counter[value] += 1

    return counter.most_common()


def print_query_results() -> None:
    type_counts = count_by_field("title")
    division_counts = count_by_field("division")

    print("Top Incident Types")
    for title, count in type_counts[:15]:
        print(f"{count:>5} | {title}")

    print("\nTop Divisions")
    for division, count in division_counts[:15]:
        print(f"{count:>5} | {division}")


if __name__ == "__main__":
    print_query_results()
