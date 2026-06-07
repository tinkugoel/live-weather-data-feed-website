"""Ingest current weather + air quality for tracked cities from Open-Meteo (no API key)."""

import csv
import datetime
import pathlib
import sys

import requests

CITIES = [
    {"name": "Bengaluru", "lat": 12.97, "lon": 77.59},
    {"name": "Delhi", "lat": 28.61, "lon": 77.21},
    {"name": "Mumbai", "lat": 19.08, "lon": 72.88},
    {"name": "Kurukshetra", "lat": 29.96, "lon": 76.83},
    {"name": "New York", "lat": 40.71, "lon": -74.01},
    {"name": "Chennai", "lat": 13.08, "lon": 80.27},
    {"name": "Gurugram", "lat": 28.45, "lon": 77.02}
]

WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
DATA_FILE = pathlib.Path("data/observations.csv")
FIELDS = [
    "timestamp_ist",
    "city",
    "temperature_c",
    "humidity_pct",
    "wind_speed_kmh",
    "precipitation_mm",
    "pm2_5",
    "pm10",
    "us_aqi",
]


def fetch_city(city: dict) -> dict:
    """Fetch current weather and air-quality readings for one city."""
    coords = {"latitude": city["lat"], "longitude": city["lon"]}

    weather = requests.get(
        WEATHER_URL,
        params={
            **coords,
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation",
        },
        timeout=30,
    )
    weather.raise_for_status()
    w = weather.json()["current"]

    air = requests.get(
        AIR_URL,
        params={**coords, "current": "pm2_5,pm10,us_aqi"},
        timeout=30,
    )
    air.raise_for_status()
    a = air.json()["current"]

    return {
        "timestamp_ist": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30))).strftime(
            "%Y-%m-%dT%H:%M:%S"
        ),
        "city": city["name"],
        "temperature_c": w["temperature_2m"],
        "humidity_pct": w["relative_humidity_2m"],
        "wind_speed_kmh": w["wind_speed_10m"],
        "precipitation_mm": w["precipitation"],
        "pm2_5": a["pm2_5"],
        "pm10": a["pm10"],
        "us_aqi": a["us_aqi"],
    }


def main() -> int:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    is_new = not DATA_FILE.exists()

    rows, failures = [], []
    for city in CITIES:
        try:
            rows.append(fetch_city(city))
        except Exception as exc:  # noqa: BLE001 - log and continue per city
            failures.append(f"{city['name']}: {exc}")

    if not rows:
        print("Ingest failed for every city:\n" + "\n".join(failures), file=sys.stderr)
        return 1

    with DATA_FILE.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerows(rows)

    print(f"Appended {len(rows)} rows to {DATA_FILE}")
    for failure in failures:
        print(f"WARNING — skipped {failure}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
