# Projekt Podsumowujący Pogodę - Tatry

## Instalacja środowiska (UV)

### 1. Instalacja UV

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**macOS / Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Po instalacji zrestartuj terminal lub odśwież zmienne środowiskowe.

---

### 2. Klonowanie repozytorium

```bash
git clone <adres-repozytorium>
cd projekt_podsumowujacy_pogoda_tatry
```

---

### 3. Instalacja zależności

```bash
uv sync
```

Polecenie automatycznie:
- pobierze wymaganą wersję Pythona (>= 3.12),
- utworzy wirtualne środowisko `.venv`,
- zainstaluje wszystkie zależności z pliku `uv.lock`.

---

### 4. Konfiguracja zmiennych środowiskowych

Utwórz plik `.env` w katalogu głównym projektu i uzupełnij klucze API:

```env
RAPIDAPI_KEY=twoj_klucz_rapidapi
OPENWEATHERAPI_KEY=twoj_klucz_openweathermap
```

---

### 5. Uruchomienie JupyterLab

```bash
uv run jupyter lab
```

---

### Przydatne polecenia UV

| Polecenie | Opis |
|-----------|------|
| `uv sync` | Instalacja/aktualizacja zależności wg `uv.lock` |
| `uv add <pakiet>` | Dodanie nowego pakietu do projektu |
| `uv remove <pakiet>` | Usunięcie pakietu z projektu |
| `uv run <komenda>` | Uruchomienie komendy w środowisku projektu |
| `uv python list` | Lista dostępnych wersji Pythona |

## Struktura katalogow

- `Scripts/` - skrypty automatyzujace (API, import do SQLite, obsluga bazy)
- `Notebooks/` - notebooki analityczne
- `data/` - pliki CSV/JSON oraz baza `weather.db`

## Szybkie komendy

- Odswiezenie danych API: `python Scripts/API.py --all`
- Import CSV do SQLite: `python Scripts/sqlite_import.py --mode replace`
