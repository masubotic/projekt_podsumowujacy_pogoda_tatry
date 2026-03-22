from __future__ import annotations

import json
from pathlib import Path

import folium
import pandas as pd
from folium.plugins import HeatMap


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
WEATHER_HISTORY_CSV = DATA_DIR / "weather_history.csv"
JSON_DIR = DATA_DIR / "json"


PARAM_LABELS = {
    "temp": "Temperatura (C)",
    "feels_like": "Odczuwalna (C)",
    "pressure": "Cisnienie (hPa)",
    "humidity": "Wilgotnosc (%)",
    "pm10": "PM10 (ug/m3)",
}


def load_weather_history() -> pd.DataFrame:
    df = pd.read_csv(WEATHER_HISTORY_CSV)
    df["download_timestamp"] = pd.to_datetime(df["download_timestamp"], format="%Y%m%d_%H%M%S")
    return df


def latest_forecast_file() -> Path | None:
    files = sorted(JSON_DIR.glob("*.json"))
    return files[-1] if files else None


def list_forecast_snapshots() -> list[tuple[pd.Timestamp, Path]]:
    snapshots: list[tuple[pd.Timestamp, Path]] = []
    for path in sorted(JSON_DIR.glob("*.json")):
        try:
            snapshot_time = pd.to_datetime(path.stem, format="%Y%m%d_%H%M%S")
        except ValueError:
            continue
        snapshots.append((snapshot_time, path))
    return snapshots


def load_forecast(path: Path) -> pd.DataFrame:
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows: list[dict] = []
    for point in raw:
        lat = point["lat"]
        lon = point["lon"]
        for forecast_time, value in point["temperatures"].items():
            rows.append(
                {
                    "lat": lat,
                    "lon": lon,
                    "forecast_time": pd.to_datetime(forecast_time),
                    "temp": float(value),
                }
            )
    return pd.DataFrame(rows)


def _normalize(series: pd.Series) -> pd.Series:
    min_v = float(series.min())
    max_v = float(series.max())
    if max_v == min_v:
        return pd.Series([0.7] * len(series), index=series.index)
    return (series - min_v) / (max_v - min_v)


def build_heatmap(df: pd.DataFrame, value_col: str, title: str) -> folium.Map:
    center_lat = float(df["lat"].mean())
    center_lon = float(df["lon"].mean())
    fmap = folium.Map(location=[center_lat, center_lon], zoom_start=10, tiles="CartoDB positron")

    weighted = _normalize(df[value_col].astype(float))
    heat_data = [[row.lat, row.lon, float(weighted.loc[idx])] for idx, row in df.iterrows()]
    HeatMap(
        heat_data,
        min_opacity=0.35,
        radius=22,
        blur=16,
        max_zoom=12,
    ).add_to(fmap)

    for _, row in df.iterrows():
        folium.CircleMarker(
            location=[float(row["lat"]), float(row["lon"])],
            radius=2,
            color="#1f2937",
            weight=1,
            fill=True,
            fill_opacity=0.6,
            popup=f"{title}: {row[value_col]:.2f}",
        ).add_to(fmap)

    return fmap
