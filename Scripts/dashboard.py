import streamlit as st
from streamlit_folium import st_folium
from io import BytesIO
import pandas as pd

from dashboard_utils import (
    HISTORICAL_CSV,
    PARAM_LABELS,
    build_ai_map,
    build_heatmap,
    get_all_points_forecast_24h,
    list_forecast_snapshots,
    load_forecast,
    load_weather_history,
)
from ai_risk import RiskAssessment, assess_risk


st.set_page_config(page_title="Dashboard pogodowy Tatry", page_icon="", layout="wide")

st.title("Dashboard pogodowy Tatry")
tab_history, tab_forecast, tab_ai, tab_export = st.tabs(
    ["Dane historyczne", "Prognoza pogody", "Ocena ryzyka AI", "Eksport danych"]
)


@st.fragment
def history_fragment():
    hist_df = load_weather_history()
    left_col, right_col = st.columns([1.5, 8.5], gap="medium")
    with left_col:
        timestamps = sorted(hist_df["download_timestamp"].dropna().unique())
        selected_timestamp = st.select_slider(
            "Czas danych",
            options=timestamps,
            format_func=lambda x: x.strftime("%Y-%m-%d %H:%M:%S"),
            value=timestamps[-1],
            key="history_timestamp",
        )
        selected_param = st.selectbox(
            "Parametr",
            options=list(PARAM_LABELS.keys()),
            format_func=lambda p: PARAM_LABELS[p],
            key="history_param",
        )

        filtered_hist = hist_df[hist_df["download_timestamp"] == selected_timestamp].copy()
        if filtered_hist.empty:
            st.warning("Brak danych.")
        else:
            st.markdown("### Podsumowanie")
            st.metric("Liczba punktow", len(filtered_hist))
            st.metric("Srednia", f"{filtered_hist[selected_param].mean():.2f}")
            st.metric("Min", f"{filtered_hist[selected_param].min():.2f}")
            st.metric("Max", f"{filtered_hist[selected_param].max():.2f}")
    with right_col:
        if filtered_hist.empty:
            st.warning("Brak danych dla wybranego timestamp.")
        else:
            hist_map = build_heatmap(filtered_hist, selected_param, PARAM_LABELS[selected_param])
            st_folium(hist_map, width=None, height=630, key="hist_map", returned_objects=[])


@st.fragment
def forecast_fragment():
    snapshots = list_forecast_snapshots()
    if not snapshots:
        st.error("Brak plikow prognozy w katalogu data/json.")
        return

    # Klucze jako stringi eliminują problem porównywania pd.Timestamp z session_state
    snapshot_labels = [t.strftime("%Y-%m-%d %H:%M:%S") for t, _ in snapshots]
    snapshot_path_map = {label: path for label, (_, path) in zip(snapshot_labels, snapshots)}

    # Obsługuje zarówno brak klucza jak i przestarzałą wartość (np. pd.Timestamp po hot-reload)
    if st.session_state.get("forecast_snapshot") not in snapshot_labels:
        st.session_state["forecast_snapshot"] = snapshot_labels[-1]

    left_col, right_col = st.columns([1.5, 8.5], gap="medium")
    with left_col:
        selected_label = st.selectbox(
            "Pobrano",
            options=snapshot_labels,
            key="forecast_snapshot",
        )
        forecast_df = load_forecast(snapshot_path_map[selected_label])
        available_times = sorted(
            pd.to_datetime(forecast_df["forecast_time"].unique()).tolist()
        )
        time_labels = [t.strftime("%Y-%m-%d %H:%M:%S") for t in available_times]
        time_map = {label: t for label, t in zip(time_labels, available_times)}

        if st.session_state.get("forecast_time") not in time_labels:
            st.session_state["forecast_time"] = time_labels[0]
        selected_time_label = st.selectbox(
            "Czas prognozy",
            options=time_labels,
            key="forecast_time",
        )
        selected_time = time_map[selected_time_label]
        filtered_forecast = forecast_df[forecast_df["forecast_time"] == selected_time].copy()
        if filtered_forecast.empty:
            st.warning("Brak danych.")
        else:
            st.markdown("### Podsumowanie")
            st.metric("Liczba punktow", len(filtered_forecast))
            st.metric("Srednia temp.", f"{filtered_forecast['temp'].mean():.2f} C")
            st.metric("Min temp.", f"{filtered_forecast['temp'].min():.2f} C")
            st.metric("Max temp.", f"{filtered_forecast['temp'].max():.2f} C")
    with right_col:
        if filtered_forecast.empty:
            st.warning("Brak punktow dla wybranego czasu prognozy.")
        else:
            forecast_map = build_heatmap(filtered_forecast, "temp", "Temperatura prognozowana (C)")
            st_folium(forecast_map, width=None, height=630, key="forecast_map", returned_objects=[])


_RISK_COLORS = {
    "safe": ("success", "Bezpieczna"),
    "risky": ("warning", "Ryzykowna"),
    "dangerous": ("error", "Niebezpieczna"),
}


@st.fragment
def ai_risk_fragment():
    snapshots = list_forecast_snapshots()
    if not snapshots:
        st.error("Brak plikow prognozy w katalogu data/json.")
        return

    snapshot_labels = [t.strftime("%Y-%m-%d %H:%M:%S") for t, _ in snapshots]
    snapshot_path_map = {label: path for label, (_, path) in zip(snapshot_labels, snapshots)}

    if st.session_state.get("ai_snapshot") not in snapshot_labels:
        st.session_state["ai_snapshot"] = snapshot_labels[-1]

    left_col, right_col = st.columns([2.5, 7.5], gap="medium")
    result: RiskAssessment | None = st.session_state.get("ai_result")

    with left_col:
        selected_label = st.selectbox("Pobrano", options=snapshot_labels, key="ai_snapshot")
        snapshot_path = snapshot_path_map[selected_label]

        st.markdown("##### Opisz lokalizację")
        user_description = st.text_area(
            label="Lokalizacja",
            placeholder="np. okolice Kasprowego Wierchu, Morskie Oko, Dolina Kościeliska...",
            height=100,
            label_visibility="collapsed",
            key="ai_description",
        )

        if st.button("Oceń ryzyko", type="primary", use_container_width=True, disabled=not user_description):
            with st.spinner("Odpytuję AI..."):
                try:
                    all_points = get_all_points_forecast_24h(snapshot_path)
                    result = assess_risk(all_points, user_description)
                    st.session_state["ai_result"] = result
                    st.session_state["ai_result_snapshot"] = selected_label
                except Exception as e:
                    st.session_state["ai_result"] = None
                    st.error(f"Błąd API: {e}")

        result = st.session_state.get("ai_result")
        if result is not None:
            rec = result.recommendation.lower()
            box_fn_name, risk_label = _RISK_COLORS.get(rec, ("info", rec))
            box_fn = getattr(st, box_fn_name)
            st.markdown("---")
            st.caption(f"Dopasowany punkt: {result.matched_description}")
            st.caption(f"lat={result.matched_lat:.5f}, lon={result.matched_lon:.5f}")
            box_fn(f"**{risk_label}**\n\n{result.justification}")

    with right_col:
        all_points = get_all_points_forecast_24h(snapshot_path)

        matched_lat = result.matched_lat if result else None
        matched_lon = result.matched_lon if result else None

        ai_map = build_ai_map(all_points, matched_lat, matched_lon)
        st_folium(ai_map, width=None, height=450, key="ai_map", returned_objects=[])

        if result is not None:
            matched_point = next(
                (p for p in all_points
                 if abs(p["lat"] - result.matched_lat) < 1e-4
                 and abs(p["lon"] - result.matched_lon) < 1e-4),
                None,
            )
            if matched_point:
                st.markdown(f"##### Prognoza 24h — {result.matched_description}")
                chart_df = pd.DataFrame(
                    {"Temperatura (°C)": list(matched_point["prognoza_24h"].values())},
                    index=list(matched_point["prognoza_24h"].keys()),
                )
                st.line_chart(chart_df, y="Temperatura (°C)")


with tab_history:
    st.caption("Heatmapa parametrow pogodowych i zanieczyszczenia PM10 z pliku weather_history.csv")
    history_fragment()

with tab_forecast:
    st.caption("Heatmapa temperatury na podstawie wybranego czasu pobrania prognozy")
    forecast_fragment()

with tab_ai:
    st.caption("Ocena ryzyka wędrówki górskiej na podstawie prognozy 24h — model Claude")
    ai_risk_fragment()

with tab_export:
    st.caption("Pobieranie danych zrodlowych do CSV i Excel")
    source = st.selectbox(
        "Zrodlo danych",
        options=["weather_history", "historical_for_eda", "forecast_json"],
        format_func=lambda x: {
            "weather_history": "Weather history (CSV)",
            "historical_for_eda": "Historical for EDA (CSV)",
            "forecast_json": "Prognoza (JSON -> tabela)",
        }[x],
    )

    if source == "weather_history":
        export_df = load_weather_history()
        base_name = "weather_history_export"
    elif source == "historical_for_eda":
        export_df = pd.read_csv(HISTORICAL_CSV)
        base_name = "historical_for_eda_export"
    else:
        snapshots = list_forecast_snapshots()
        if not snapshots:
            st.error("Brak plikow prognozy w katalogu data/json.")
            st.stop()
        snapshot_times = [item[0] for item in snapshots]
        selected_snapshot = st.selectbox(
            "Pobrano",
            options=snapshot_times,
            format_func=lambda x: x.strftime("%Y-%m-%d %H:%M:%S"),
            index=len(snapshot_times) - 1,
            key="export_snapshot",
        )
        selected_snapshot_path = dict(snapshots)[selected_snapshot]
        export_df = load_forecast(selected_snapshot_path)
        base_name = f"forecast_export_{selected_snapshot.strftime('%Y%m%d_%H%M%S')}"

    st.write(f"Liczba rekordow: {len(export_df)}")
    st.dataframe(export_df.head(20), width="stretch")

    csv_bytes = export_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Pobierz CSV",
        data=csv_bytes,
        file_name=f"{base_name}.csv",
        mime="text/csv",
    )

    excel_buffer = BytesIO()
    export_df.to_excel(excel_buffer, index=False, sheet_name="dane")
    excel_buffer.seek(0)
    st.download_button(
        "Pobierz Excel",
        data=excel_buffer,
        file_name=f"{base_name}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
