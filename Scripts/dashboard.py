import base64
import streamlit as st
from streamlit_folium import st_folium
from io import BytesIO
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go

from dashboard_utils import (
    HISTORICAL_CSV,
    PARAM_LABELS,
    PROJECT_ROOT,
    build_ai_map,
    build_heatmap,
    get_all_points_forecast_24h,
    list_forecast_snapshots,
    load_forecast,
    load_weather_history,
)
from ai_risk import MatchedPoint, RiskAssessment, assess_risk


st.set_page_config(page_title="Dashboard pogodowy Tatry", page_icon="", layout="wide")

_logo_b64 = base64.b64encode((PROJECT_ROOT / "grafika.png").read_bytes()).decode()
st.markdown(
    f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:24px">'
    f'<img src="data:image/png;base64,{_logo_b64}" style="width:132px;height:auto">'
    f'<h1 style="margin:0;padding:0">Dashboard pogodowy Tatry</h1>'
    f'</div>',
    unsafe_allow_html=True,
)
tab_ai, tab_history, tab_forecast, tab_export = st.tabs(
    ["Ocena ryzyka AI", "Dane historyczne", "Prognoza pogody", "Eksport danych"]
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
            options=[None] + list(PARAM_LABELS.keys()),
            format_func=lambda p: "Wybierz parametr..." if p is None else PARAM_LABELS[p],
            key="history_param",
        )

        filtered_hist = None
        if selected_param is not None:
            filtered_hist = hist_df[hist_df["download_timestamp"] == selected_timestamp].copy()
            if filtered_hist.empty:
                st.warning("Brak danych.")
                filtered_hist = None
            else:
                st.markdown("### Podsumowanie")
                st.metric("Liczba punktow", len(filtered_hist))
                st.metric("Srednia", f"{filtered_hist[selected_param].mean():.2f}")
                st.metric("Min", f"{filtered_hist[selected_param].min():.2f}")
                st.metric("Max", f"{filtered_hist[selected_param].max():.2f}")
    with right_col:
        if filtered_hist is not None:
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

        time_labels_with_none = [None] + time_labels
        if st.session_state.get("forecast_time") not in time_labels_with_none:
            st.session_state["forecast_time"] = None
        selected_time_label = st.selectbox(
            "Czas prognozy",
            options=time_labels_with_none,
            format_func=lambda x: "Wybierz czas prognozy..." if x is None else x,
            key="forecast_time",
        )

        filtered_forecast = None
        if selected_time_label is not None:
            selected_time = time_map[selected_time_label]
            filtered_forecast = forecast_df[forecast_df["forecast_time"] == selected_time].copy()
            if filtered_forecast.empty:
                st.warning("Brak danych.")
                filtered_forecast = None
            else:
                st.markdown("### Podsumowanie")
                st.metric("Liczba punktow", len(filtered_forecast))
                st.metric("Srednia temp.", f"{filtered_forecast['temp'].mean():.2f} C")
                st.metric("Min temp.", f"{filtered_forecast['temp'].min():.2f} C")
                st.metric("Max temp.", f"{filtered_forecast['temp'].max():.2f} C")
    with right_col:
        if filtered_forecast is not None:
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

    with left_col:
        selected_label = st.selectbox("Pobrano", options=snapshot_labels, key="ai_snapshot")
        snapshot_path = snapshot_path_map[selected_label]

        st.markdown("##### Opisz lokalizację")
        user_description = st.text_input(
            label="Lokalizacja",
            placeholder="np. okolice Kasprowego Wierchu, Morskie Oko...",
            label_visibility="collapsed",
            key="ai_description",
        )

        # Trigger AI gdy opis zmienił się względem ostatniego zapytania
        if user_description and user_description != st.session_state.get("_last_ai_description"):
            st.session_state["_last_ai_description"] = user_description
            with st.spinner("Odpytuję AI..."):
                try:
                    all_points = get_all_points_forecast_24h(snapshot_path)
                    result = assess_risk(all_points, user_description)
                    st.session_state["ai_result"] = result
                except Exception as e:
                    st.session_state["ai_result"] = None
                    st.error(f"Błąd API: {e}")
            st.rerun(scope="fragment")

    result: RiskAssessment | None = st.session_state.get("ai_result")
    all_points = get_all_points_forecast_24h(snapshot_path)

    with right_col:
        if result is not None:
            if not result.in_tatry:
                st.info("Dashboard obsługuje wyłącznie obszar Tatr. Podana lokalizacja znajduje się poza zasięgiem danych.")
            else:
                rec = result.recommendation.lower()
                box_fn_name, risk_label = _RISK_COLORS.get(rec, ("info", rec))
                getattr(st, box_fn_name)(f"**{risk_label}**\n\n{result.justification}")

        matched_coords = (
            [(mp.lat, mp.lon, mp.description) for mp in result.matched_points]
            if (result and result.in_tatry and result.matched_points)
            else None
        )

        map_col, chart_col = st.columns(2, gap="medium")

        with map_col:
            ai_map = build_ai_map(all_points, matched_coords)
            st_folium(ai_map, width=None, height=420, key="ai_map", returned_objects=[])

        with chart_col:
            if result is not None and result.in_tatry and result.matched_points:
                fig = go.Figure()
                for mp in result.matched_points:
                    point_data = next(
                        (p for p in all_points
                         if abs(p["lat"] - mp.lat) < 1e-4
                         and abs(p["lon"] - mp.lon) < 1e-4),
                        None,
                    )
                    if point_data:
                        tick_labels = [t[:16] for t in point_data["prognoza_24h"].keys()]
                        temps = list(point_data["prognoza_24h"].values())
                        fig.add_trace(go.Scatter(
                            x=tick_labels, y=temps,
                            mode="lines+markers",
                            name=mp.description,
                            marker=dict(size=5),
                        ))
                if fig.data:
                    title = "Prognoza 24h — trasa" if len(result.matched_points) > 1 else \
                            f"Prognoza 24h — {result.matched_points[0].description}"
                    st.markdown(f"##### {title}")
                    fig.update_layout(
                        xaxis=dict(tickangle=45),
                        yaxis_title="Temperatura (°C)",
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                        margin=dict(t=40, b=10, l=10, r=10),
                        height=380,
                    )
                    st.plotly_chart(fig, use_container_width=True)


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
