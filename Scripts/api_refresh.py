from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv
from tqdm import tqdm


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
JSON_DIR = DATA_DIR / "json"
HISTORICAL_CSV = DATA_DIR / "historical_for_eda.csv"
WEATHER_HISTORY_CSV = DATA_DIR / "weather_history.csv"

STATIONS = {
    "12625": "Zakopane",
    "12650": "Kasprowy Wierch",
}

LAT_MIN = 49.17035070524409
LAT_MAX = 49.309555578150245
LON_MIN = 19.76220706945233
LON_MAX = 20.125423430066586


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Brak zmiennej srodowiskowej: {name}")
    return value


def _lat_lon_grid(size: int) -> list[tuple[float, float]]:
    lats = np.linspace(LAT_MIN, LAT_MAX, size)
    lons = np.linspace(LON_MIN, LON_MAX, size)
    return [(float(lat), float(lon)) for lat in lats for lon in lons]


def _openweather_params(lat: float, lon: float, api_key: str) -> dict:
    return {"lat": lat, "lon": lon, "appid": api_key, "units": "metric"}


def refresh_historical(start: str, end: str, rapidapi_key: str) -> Path:
    records: list[pd.DataFrame] = []
    columns_map = {
        "tavg": "avg_temp",
        "tmin": "min_temp",
        "tmax": "max_temp",
        "prcp": "precipitation_total_mm",
        "wdir": "wind_direction",
        "wspd": "average_wind_speed",
        "wpgt": "max_wind_speed",
        "pres": "pressure_hpa",
        "tsun": "sunshine_total_min",
    }
    headers = {
        "x-rapidapi-key": rapidapi_key,
        "x-rapidapi-host": "meteostat.p.rapidapi.com",
        "Content-Type": "application/json",
    }

    for station_id, station_name in STATIONS.items():
        response = requests.get(
            "https://meteostat.p.rapidapi.com/stations/daily",
            headers=headers,
            params={"station": station_id, "start": start, "end": end},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json().get("data", [])
        station_df = pd.DataFrame(data)
        if station_df.empty:
            continue
        station_df["station_name"] = station_name
        records.append(station_df)

    historical_df = pd.concat(records, axis=0).reset_index(drop=True) if records else pd.DataFrame()
    if not historical_df.empty:
        historical_df = historical_df.rename(columns_map, axis=1)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    historical_df.to_csv(HISTORICAL_CSV, index=False)
    return HISTORICAL_CSV


def refresh_current_weather(openweather_key: str, grid_size: int, append: bool) -> Path:
    rows: list[dict] = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for lat, lon in tqdm(_lat_lon_grid(grid_size), desc="OpenWeather current"):
        weather_response = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params=_openweather_params(lat, lon, openweather_key),
            timeout=30,
        )
        weather_response.raise_for_status()
        main = weather_response.json().get("main", {})

        air_response = requests.get(
            "https://api.openweathermap.org/data/2.5/air_pollution",
            params={"lat": lat, "lon": lon, "appid": openweather_key},
            timeout=30,
        )
        air_response.raise_for_status()
        pm10 = air_response.json()["list"][0]["components"]["pm10"]

        row = {
            "temp": main.get("temp"),
            "feels_like": main.get("feels_like"),
            "pressure": main.get("pressure"),
            "humidity": main.get("humidity"),
            "lat": lat,
            "lon": lon,
            "pm10": pm10,
            "download_timestamp": timestamp,
        }
        rows.append(row)

    current_df = pd.DataFrame(rows)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    write_mode = "a" if append else "w"
    include_header = not WEATHER_HISTORY_CSV.exists() or not append
    current_df.to_csv(
        WEATHER_HISTORY_CSV,
        mode=write_mode,
        header=include_header,
        index=False,
    )
    return WEATHER_HISTORY_CSV


def refresh_forecast(openweather_key: str, grid_size: int) -> Path:
    forecast_data: list[dict] = []
    for lat, lon in tqdm(_lat_lon_grid(grid_size), desc="OpenWeather forecast"):
        response = requests.get(
            "https://api.openweathermap.org/data/2.5/forecast",
            params=_openweather_params(lat, lon, openweather_key),
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json().get("list", [])
        temperatures = {item["dt_txt"]: item["main"]["temp"] for item in payload}
        forecast_data.append({"lat": lat, "lon": lon, "temperatures": temperatures})

    JSON_DIR.mkdir(parents=True, exist_ok=True)
    file_path = JSON_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with file_path.open("w", encoding="utf-8") as handle:
        json.dump(forecast_data, handle, indent=2)
    return file_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Odswiezanie danych pogodowych z API (Meteostat + OpenWeather)."
    )
    parser.add_argument("--all", action="store_true", help="Uruchom wszystkie kroki.")
    parser.add_argument("--historical", action="store_true", help="Odswiez historical_for_eda.csv.")
    parser.add_argument("--current", action="store_true", help="Odswiez weather_history.csv.")
    parser.add_argument("--forecast", action="store_true", help="Zapisz nowy plik prognozy JSON.")
    parser.add_argument("--start", default="2020-01-01", help="Data start dla Meteostat (YYYY-MM-DD).")
    parser.add_argument(
        "--end",
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Data koncowa dla Meteostat (YYYY-MM-DD).",
    )
    parser.add_argument("--grid-size", type=int, default=10, help="Rozmiar siatki lat/lon (N x N).")
    parser.add_argument(
        "--weather-mode",
        choices=["append", "replace"],
        default="append",
        help="Tryb zapisu weather_history.csv.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_dotenv()

    run_historical = args.all or args.historical
    run_current = args.all or args.current
    run_forecast = args.all or args.forecast

    if not (run_historical or run_current or run_forecast):
        run_historical = run_current = run_forecast = True

    outputs: list[str] = []

    if run_historical:
        rapidapi_key = _required_env("RAPIDAPI_KEY")
        path = refresh_historical(start=args.start, end=args.end, rapidapi_key=rapidapi_key)
        outputs.append(f"historical: {path}")

    if run_current:
        openweather_key = _required_env("OPENWEATHERAPI_KEY")
        path = refresh_current_weather(
            openweather_key=openweather_key,
            grid_size=args.grid_size,
            append=args.weather_mode == "append",
        )
        outputs.append(f"current: {path}")

    if run_forecast:
        openweather_key = _required_env("OPENWEATHERAPI_KEY")
        path = refresh_forecast(openweather_key=openweather_key, grid_size=args.grid_size)
        outputs.append(f"forecast: {path}")

    print("Zakonczono odswiezanie:")
    for item in outputs:
        print(f"- {item}")


if __name__ == "__main__":
    main()
