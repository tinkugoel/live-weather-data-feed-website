"""Transform raw observations with DuckDB and emit site/data.json for the dashboard."""

import datetime
import json
import pathlib

import duckdb

DATA_FILE = pathlib.Path("data/observations.csv")
OUT_FILE = pathlib.Path("site/data.json")

LATEST_SQL = """
    SELECT timestamp_ist, city, temperature_c, humidity_pct, wind_speed_kmh,
           precipitation_mm, pm2_5, pm10, us_aqi
    FROM obs
    QUALIFY row_number() OVER (PARTITION BY city ORDER BY timestamp_ist DESC) = 1
    ORDER BY city
"""

SERIES_SQL = """
    SELECT timestamp_ist, city, temperature_c, us_aqi
    FROM obs
    QUALIFY row_number() OVER (PARTITION BY city ORDER BY timestamp_ist DESC) <= 56
    ORDER BY city, timestamp_ist
"""

DAILY_SQL = """
    SELECT
        strftime(CAST(timestamp_ist AS TIMESTAMP), '%Y-%m-%d') AS day,
        city,
        round(avg(temperature_c), 1)  AS avg_temperature_c,
        round(min(temperature_c), 1)  AS min_temperature_c,
        round(max(temperature_c), 1)  AS max_temperature_c,
        round(avg(us_aqi), 0)         AS avg_us_aqi,
        round(max(pm2_5), 1)          AS max_pm2_5,
        count(*)                      AS observations
    FROM obs
    GROUP BY 1, 2
    ORDER BY 1 DESC, 2
"""


def rows_as_dicts(con: duckdb.DuckDBPyConnection, sql: str) -> list[dict]:
    cursor = con.execute(sql)
    columns = [d[0] for d in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def build_payload(data_file: pathlib.Path = DATA_FILE) -> dict:
    con = duckdb.connect()
    path = str(data_file).replace("'", "''")
    con.execute(f"CREATE VIEW obs AS SELECT * FROM read_csv_auto('{path}', header=true)")
    total, cities, first_seen = con.execute(
        "SELECT count(*), count(DISTINCT city), min(timestamp_ist) FROM obs"
    ).fetchone()

    return {
        "generated_at_ist": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30))).strftime(
            "%Y-%m-%dT%H:%M:%S"
        ),
        "stats": {
            "total_observations": total,
            "cities": cities,
            "collecting_since": str(first_seen),
        },
        "latest": rows_as_dicts(con, LATEST_SQL),
        "series": rows_as_dicts(con, SERIES_SQL),
        "daily": rows_as_dicts(con, DAILY_SQL),
    }


def main() -> int:
    payload = build_payload()
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(payload, default=str, indent=1))
    print(
        f"Wrote {OUT_FILE} — {payload['stats']['total_observations']} observations, "
        f"{payload['stats']['cities']} cities"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
