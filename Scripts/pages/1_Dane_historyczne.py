import streamlit as st
from streamlit_folium import st_folium
from pathlib import Path
import sys

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from dashboard_utils import PARAM_LABELS, build_heatmap, load_weather_history


st.title("Dane historyczne")
st.caption("Heatmapa parametrów pogodowych i zanieczyszczenia PM10 z pliku weather_history.csv")

df = load_weather_history()

timestamps = sorted(df["download_timestamp"].dropna().unique())
selected_timestamp = st.selectbox(
    "Wybierz czas pobrania danych",
    options=timestamps,
    format_func=lambda x: x.strftime("%Y-%m-%d %H:%M:%S"),
    index=len(timestamps) - 1,
)

selected_param = st.selectbox(
    "Wybierz parametr do heatmapy",
    options=list(PARAM_LABELS.keys()),
    format_func=lambda p: PARAM_LABELS[p],
)

filtered = df[df["download_timestamp"] == selected_timestamp].copy()
if filtered.empty:
    st.warning("Brak danych dla wybranego timestamp.")
else:
    st.metric("Liczba punktow", len(filtered))
    st.metric("Srednia wartosc", f"{filtered[selected_param].mean():.2f}")
    fmap = build_heatmap(filtered, selected_param, PARAM_LABELS[selected_param])
    st_folium(fmap, width=None, height=650)
