import streamlit as st
from streamlit_folium import st_folium
from pathlib import Path
import sys

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from dashboard_utils import build_heatmap, latest_forecast_file, load_forecast


st.title("Prognoza pogody")
st.caption("Heatmapa temperatury z najnowszego pliku prognozy JSON")

forecast_path = latest_forecast_file()
if forecast_path is None:
    st.error("Brak plikow prognozy w katalogu data/json.")
    st.stop()

st.info(f"Zrodlo prognozy: {forecast_path.name}")
df = load_forecast(forecast_path)

available_times = sorted(df["forecast_time"].unique())
selected_time = st.selectbox(
    "Wybierz horyzont prognozy",
    options=available_times,
    format_func=lambda x: x.strftime("%Y-%m-%d %H:%M:%S"),
    index=0,
)

filtered = df[df["forecast_time"] == selected_time].copy()
if filtered.empty:
    st.warning("Brak punktow dla wybranego czasu prognozy.")
else:
    st.metric("Liczba punktow", len(filtered))
    st.metric("Srednia temperatura", f"{filtered['temp'].mean():.2f} C")
    fmap = build_heatmap(filtered, "temp", "Temperatura prognozowana (C)")
    st_folium(fmap, width=None, height=650)
