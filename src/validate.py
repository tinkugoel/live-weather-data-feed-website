"""Data-quality gate: fail the pipeline if the dataset violates schema or range checks."""

import pathlib
import sys

import duckdb

DATA_FILE = pathlib.Path("data/observations.csv")

CHECKS = {
    "null keys": """
        SELECT count(*) FROM obs
        WHERE timestamp_ist IS NULL OR city IS NULL OR trim(city) = ''
    """,
    "temperature out of range (-60..60 C)": """
        SELECT count(*) FROM obs WHERE temperature_c NOT BETWEEN -60 AND 60
    """,
    "humidity out of range (0..100)": """
        SELECT count(*) FROM obs WHERE humidity_pct NOT BETWEEN 0 AND 100
    """,
    "negative particulate readings": """
        SELECT count(*) FROM obs WHERE pm2_5 < 0 OR pm10 < 0
    """,
    "AQI out of range (0..1000)": """
        SELECT count(*) FROM obs WHERE us_aqi NOT BETWEEN 0 AND 1000
    """,
    "duplicate (timestamp, city) rows": """
        SELECT count(*) FROM (
            SELECT timestamp_ist, city FROM obs
            GROUP BY 1, 2 HAVING count(*) > 1
        )
    """,
}


def validate(data_file: pathlib.Path = DATA_FILE) -> list[str]:
    """Run all checks; return a list of human-readable failures (empty = pass)."""
    con = duckdb.connect()
    path = str(data_file).replace("'", "''")
    con.execute(f"CREATE VIEW obs AS SELECT * FROM read_csv_auto('{path}', header=true)")

    failures = []
    for name, query in CHECKS.items():
        bad = con.execute(query).fetchone()[0]
        if bad:
            failures.append(f"{name}: {bad} offending row(s)")
    return failures


def main() -> int:
    if not DATA_FILE.exists():
        print(f"No data file at {DATA_FILE}; nothing to validate.", file=sys.stderr)
        return 1

    failures = validate()
    if failures:
        print("DATA VALIDATION FAILED:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    print("All data-quality checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
