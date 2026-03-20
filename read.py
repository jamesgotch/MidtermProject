import sqlite3

from models import DATABASE_PATH


def fetch_incident_type_counts() -> list[tuple[str, int]]:
    with sqlite3.connect(DATABASE_PATH) as connection:
        rows = connection.execute(
            """
            SELECT title, COUNT(*) AS incident_count
            FROM incident
            WHERE title IS NOT NULL AND title != ''
            GROUP BY title
            ORDER BY incident_count DESC
            """
        ).fetchall()
    return [(row[0], row[1]) for row in rows]


def fetch_division_counts() -> list[tuple[str, int]]:
    with sqlite3.connect(DATABASE_PATH) as connection:
        rows = connection.execute(
            """
            SELECT division, COUNT(*) AS incident_count
            FROM incident
            WHERE division IS NOT NULL AND division != ''
            GROUP BY division
            ORDER BY incident_count DESC
            """
        ).fetchall()
    return [(row[0], row[1]) for row in rows]


def print_query_results() -> None:
    type_counts = fetch_incident_type_counts()
    division_counts = fetch_division_counts()

    pd = None
    try:
        import pandas as pd  # type: ignore[import-not-found]
    except ImportError:
        pd = None

    if pd is not None:
        print("Top Incident Types")
        print(pd.DataFrame(type_counts, columns=["title", "incident_count"]).head(15))
        print()
        print("Top Divisions")
        print(pd.DataFrame(division_counts, columns=["division", "incident_count"]).head(15))
        return

    print("Top Incident Types")
    for title, count in type_counts[:15]:
        print(f"{count:>5} | {title}")

    print("\nTop Divisions")
    for division, count in division_counts[:15]:
        print(f"{count:>5} | {division}")


if __name__ == "__main__":
    print_query_results()
