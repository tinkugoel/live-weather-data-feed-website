"""Unit tests for validate and transform stages using synthetic data."""

import csv
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from ingest import FIELDS  # noqa: E402
from transform import build_payload  # noqa: E402
from validate import validate  # noqa: E402

GOOD_ROWS = [
    {
        "timestamp_ist": "2026-06-07T00:00:00Z",
        "city": "Bengaluru",
        "temperature_c": 24.5,
        "humidity_pct": 60,
        "wind_speed_kmh": 10.2,
        "precipitation_mm": 0.0,
        "pm2_5": 18.0,
        "pm10": 40.0,
        "us_aqi": 64,
    },
    {
        "timestamp_ist": "2026-06-07T06:00:00Z",
        "city": "Bengaluru",
        "temperature_c": 28.1,
        "humidity_pct": 52,
        "wind_speed_kmh": 12.0,
        "precipitation_mm": 0.2,
        "pm2_5": 22.0,
        "pm10": 45.0,
        "us_aqi": 71,
    },
    {
        "timestamp_ist": "2026-06-07T00:00:00Z",
        "city": "London",
        "temperature_c": 14.0,
        "humidity_pct": 80,
        "wind_speed_kmh": 22.5,
        "precipitation_mm": 1.1,
        "pm2_5": 8.0,
        "pm10": 15.0,
        "us_aqi": 33,
    },
]


def write_csv(path: pathlib.Path, rows: list[dict]) -> pathlib.Path:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_validate_passes_on_clean_data(tmp_path):
    data = write_csv(tmp_path / "obs.csv", GOOD_ROWS)
    assert validate(data) == []


def test_validate_catches_out_of_range_and_duplicates(tmp_path):
    bad = GOOD_ROWS + [
        {**GOOD_ROWS[0]},  # exact duplicate (timestamp, city)
        {**GOOD_ROWS[2], "temperature_c": 99.0, "us_aqi": 700},
    ]
    data = write_csv(tmp_path / "obs.csv", bad)
    failures = validate(data)
    assert any("temperature" in f for f in failures)
    assert any("AQI" in f for f in failures)
    assert any("duplicate" in f for f in failures)


def test_build_payload_shapes(tmp_path):
    data = write_csv(tmp_path / "obs.csv", GOOD_ROWS)
    payload = build_payload(data)

    assert payload["stats"]["total_observations"] == 3
    assert payload["stats"]["cities"] == 2

    # latest: one row per city, the most recent one
    latest = {r["city"]: r for r in payload["latest"]}
    assert set(latest) == {"Bengaluru", "London"}
    assert latest["Bengaluru"]["temperature_c"] == 28.1

    # daily aggregates computed correctly
    blr_daily = next(
        r for r in payload["daily"] if r["city"] == "Bengaluru" and r["day"] == "2026-06-07"
    )
    assert blr_daily["observations"] == 2
    assert blr_daily["min_temperature_c"] == 24.5
    assert blr_daily["max_temperature_c"] == 28.1

    # series rows carry the chart fields
    assert {"timestamp_ist", "city", "temperature_c", "us_aqi"} <= set(payload["series"][0])
