"""Ingest current weather + air quality for tracked cities from Open-Meteo (no API key)."""

import csv
import datetime
import pathlib
import sys

import requests_cache
import openmeteo_requests
from retry_requests import retry

CITIES = [
    {"name": "Bengaluru", "lat": 12.9716, "lon": 77.5946},
    {"name": "Delhi", "lat": 28.6448, "lon": 77.2167},
    {"name": "Mumbai", "lat": 19.0761, "lon": 72.8774},
    # {"name": "Kurukshetra", "lat": 29.9695, "lon": 76.8783},
    {"name": "New York", "lat": 40.7128, "lon": -74.0060},
    {"name": "Chennai", "lat": 13.0878, "lon": 80.2785},
    {"name": "Gurugram", "lat": 28.4575, "lon": 77.0263}
]

# Setup the Open-Meteo API client with cache and retry on error
cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
openmeteo = openmeteo_requests.Client(session = retry_session)


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

    weather = openmeteo.weather_api(
        WEATHER_URL,
        params={
            **coords,
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation",
            "timezone": "IST"
        },
        timeout=30,
    )
    
    w = weather[0].Current()

    air = openmeteo.weather_api(
        AIR_URL,
        params={**coords, "current": "pm2_5,pm10,us_aqi"},
        timeout=30,
    )
    
    a = air[0].Current()

    return {
        "timestamp_ist": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30))).strftime(
            "%Y-%m-%dT%H:%M:%S"
        ),
        "city": city["name"],
        "temperature_c": round(w.Variables(0).Value(), 1),
        "humidity_pct": int(w.Variables(1).Value()),
        "wind_speed_kmh": round(w.Variables(2).Value(), 1),
        "precipitation_mm": round(w.Variables(3).Value(), 1),
        "pm2_5": round(a.Variables(0).Value(), 1),
        "pm10": round(a.Variables(1).Value(), 1),
        "us_aqi": int(a.Variables(2).Value()),
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
