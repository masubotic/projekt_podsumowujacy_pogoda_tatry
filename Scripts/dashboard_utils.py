from __future__ import annotations

import json
from pathlib import Path

import folium
import pandas as pd
import streamlit as st
from branca.element import Element
from folium.plugins import HeatMap


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
WEATHER_HISTORY_CSV = DATA_DIR / "weather_history.csv"
HISTORICAL_CSV = DATA_DIR / "historical_for_eda.csv"
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


@st.cache_data(show_spinner=False)
def get_all_points_forecast_24h(path: Path) -> list[dict]:
    """Zwraca pierwsze 8 odczytów temperatury (24h co 3h) dla wszystkich punktów siatki."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [
        {
            "lat": round(point["lat"], 5),
            "lon": round(point["lon"], 5),
            "prognoza_24h": dict(list(point["temperatures"].items())[:8]),
        }
        for point in raw
    ]


def build_ai_map(
    all_points: list[dict],
    matched_points: list[tuple[float, float, str]] | None = None,
) -> folium.Map:
    """
    Buduje mapę ze wszystkimi punktami siatki.
    matched_points: lista krotek (lat, lon, description) dopasowanych punktów/trasy.
    """
    lats = [p["lat"] for p in all_points]
    lons = [p["lon"] for p in all_points]
    fmap = folium.Map(
        location=[sum(lats) / len(lats), sum(lons) / len(lons)],
        zoom_start=10,
        tiles="CartoDB positron",
    )

    matched_set = {
        (round(lat, 4), round(lon, 4))
        for lat, lon, _ in (matched_points or [])
    }

    for p in all_points:
        if (round(p["lat"], 4), round(p["lon"], 4)) in matched_set:
            continue  # matched points rendered separately below
        folium.CircleMarker(
            location=[p["lat"], p["lon"]],
            radius=4,
            color="#1f2937",
            weight=1,
            fill=True,
            fill_color="#6b7280",
            fill_opacity=0.5,
        ).add_to(fmap)

    if matched_points:
        coords = [(lat, lon) for lat, lon, _ in matched_points]

        # Linia trasy gdy więcej niż jeden punkt
        if len(coords) > 1:
            folium.PolyLine(coords, color="#dc2626", weight=3, opacity=0.8).add_to(fmap)

        for i, (lat, lon, desc) in enumerate(matched_points):
            label = f"Start: {desc}" if i == 0 and len(matched_points) > 1 else \
                    f"Meta: {desc}" if i == len(matched_points) - 1 and len(matched_points) > 1 else desc
            folium.Marker(
                location=[lat, lon],
                icon=folium.Icon(color="red", icon="star"),
                popup=label,
            ).add_to(fmap)

    return fmap


@st.cache_data(show_spinner=False)
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


@st.cache_data(show_spinner=False)
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

    # Leaflet buforuje wymiary kontenera — po ukryciu taba getSize() wciąż zwraca 0,
    # nawet gdy kontener jest już widoczny. Śledzimy clientWidth/clientHeight (rzeczywisty DOM)
    # i wywołujemy invalidateSize() tylko gdy rozmiar faktycznie się zmienia (0→N lub resize).
    fmap.get_root().html.add_child(Element("""
    <script>
    (function () {
        var prevSizes = new WeakMap();

        function fixMap(el) {
            if (!el._leaflet_map) return;
            var w = el.clientWidth;
            var h = el.clientHeight;
            var prev = prevSizes.get(el);
            var changed = !prev || prev.w !== w || prev.h !== h;
            prevSizes.set(el, {w: w, h: h});
            if (changed && w > 0 && h > 0) {
                el._leaflet_map.invalidateSize({animate: false, pan: false});
            }
        }

        function fixAll() {
            document.querySelectorAll('.leaflet-container').forEach(fixMap);
        }

        // Szybki polling dopóki kontenery Leafleta się nie pojawią
        var initId = setInterval(function () {
            if (document.querySelector('.leaflet-container')) {
                clearInterval(initId);
                fixAll();
            }
        }, 50);

        // Stały polling do wykrywania przejść hidden→visible przy zmianie taba
        setInterval(fixAll, 500);
    })();
    </script>
    """))

    return fmap
