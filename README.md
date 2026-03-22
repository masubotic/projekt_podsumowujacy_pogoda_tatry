# Dashboard pogodowy Tatry

**Live:** [https://pogodatatry.streamlit.app/](https://pogodatatry.streamlit.app/)

Interaktywny dashboard prezentujący dane pogodowe dla obszaru Tatr. Dane są automatycznie odświeżane co tydzień przez GitHub Actions.

## Co robi dashboard

Dashboard składa się z czterech zakładek:

- **Ocena ryzyka AI** — użytkownik opisuje lokalizację lub trasę wędrówki (np. „Kasprowy Wierch", „z Zakopanego przez Dolinę Pięciu Stawów na Rysy"), a model Claude ocenia ryzyko wycieczki na podstawie 24-godzinnej prognozy temperatury. Wynik (bezpieczna / ryzykowna / niebezpieczna) pojawia się wraz z uzasadnieniem, zaznaczoną trasą na mapie i wykresem temperatury.
- **Dane historyczne** — heatmapa parametrów pogodowych (temperatura, odczuwalna, ciśnienie, wilgotność, PM10) dla wybranego momentu pobrania danych.
- **Prognoza pogody** — heatmapa prognozowanej temperatury dla wybranego czasu z wybranego snapshotu prognozy.
- **Eksport danych** — pobieranie danych źródłowych w formacie CSV lub Excel.

## Jak działa

Dane pobierane są z dwóch źródeł:
- **OpenWeatherMap API** — bieżące warunki pogodowe i prognozy 5-dniowe dla siatki 10×10 punktów pokrywającej Tatry (lat 49.17–49.31, lon 19.76–20.13)
- **Meteostat (RapidAPI)** — historyczne dane dobowe ze stacji Zakopane i Kasprowy Wierch

Ocena ryzyka korzysta z modelu `claude-sonnet-4-6` przez OpenRouter API.

---

## Uruchomienie lokalne

### 1. Instalacja uv

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**macOS / Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Po instalacji zrestartuj terminal lub odśwież zmienne środowiskowe.

### 2. Klonowanie repozytorium

```bash
git clone <adres-repozytorium>
cd projekt_podsumowujacy_pogoda_tatry
```

### 3. Instalacja zależności

```bash
uv sync
```

Polecenie automatycznie pobierze wymaganą wersję Pythona (>= 3.12), utworzy wirtualne środowisko `.venv` i zainstaluje wszystkie zależności z `uv.lock`.

### 4. Konfiguracja kluczy API

Utwórz plik `.env` w katalogu głównym projektu:

```env
OPENROUTER_API_KEY=twoj_klucz_openrouter
OPENWEATHERAPI_KEY=twoj_klucz_openweathermap
RAPIDAPI_KEY=twoj_klucz_rapidapi
```

Klucz `OPENROUTER_API_KEY` jest wymagany do działania zakładki **Ocena ryzyka AI**. Pozostałe dwa są potrzebne wyłącznie do ręcznego odświeżania danych.

### 5. Uruchomienie dashboardu

```bash
uv run streamlit run Scripts/dashboard.py
```

Dashboard otworzy się automatycznie w przeglądarce pod adresem `http://localhost:8501`.

---

## Odświeżanie danych

Dane są odświeżane automatycznie co poniedziałek przez GitHub Actions (workflow `.github/workflows/refresh_data.yml`). Workflow pobiera aktualne dane z API i commituje zaktualizowane pliki do katalogu `data/`.

Aby odświeżyć dane ręcznie:

```bash
uv run python Scripts/api_refresh.py --all
```

Dostępne flagi: `--historical`, `--current`, `--forecast`, `--all`.

---

## Struktura projektu

```
├── Scripts/
│   ├── dashboard.py        # Główna aplikacja Streamlit
│   ├── dashboard_utils.py  # Funkcje pomocnicze (mapy, wykresy, ładowanie danych)
│   ├── ai_risk.py          # Ocena ryzyka przez Claude API
│   └── api_refresh.py      # Pobieranie danych z API
├── Notebooks/              # Notebooki analityczne (EDA, prototypy)
├── data/
│   ├── weather_history.csv # Bieżące dane pogodowe (siatka punktów)
│   ├── historical_for_eda.csv # Dane historyczne (stacje meteorologiczne)
│   └── json/               # Snapshoty prognoz (jeden plik JSON = jeden moment pobrania)
├── .github/workflows/
│   └── refresh_data.yml    # Automatyczne odświeżanie danych co tydzień
└── .streamlit/
    └── config.toml         # Konfiguracja Streamlit
```
