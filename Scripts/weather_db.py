import sqlite3
from collections.abc import Iterable
from csv import DictReader, reader
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_DB_PATH = DATA_DIR / "weather.db"


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS weather_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    observed_at TEXT NOT NULL,
    location TEXT NOT NULL,
    temperature_c REAL NOT NULL,
    humidity INTEGER,
    pressure_hpa INTEGER,
    wind_speed_ms REAL,
    weather_description TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


def _db_path() -> Path:
    return DEFAULT_DB_PATH


def initialize_weather_database(db_path: Path | None = None) -> Path:
    target = db_path or _db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(target) as conn:
        conn.execute(CREATE_TABLE_SQL)
        conn.commit()
    return target


def _normalize_observed_at(value: str) -> str:
    parsed = datetime.strptime(value, "%Y%m%d_%H%M%S")
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


def _build_location(lat: str | float, lon: str | float) -> str:
    return f"Tatry ({float(lat):.5f}, {float(lon):.5f})"


def _rows_from_header_csv(csv_path: Path) -> Iterable[tuple]:
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        for row in DictReader(handle):
            yield (
                _normalize_observed_at(row["download_timestamp"]),
                _build_location(row["lat"], row["lon"]),
                float(row["temp"]),
                int(row["humidity"]),
                int(row["pressure"]),
                None,
                f"pm10={row['pm10']}",
            )


def _rows_from_legacy_csv(csv_path: Path) -> Iterable[tuple]:
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        for row in reader(handle):
            if not row:
                continue
            yield (
                _normalize_observed_at(row[7]),
                _build_location(row[4], row[5]),
                float(row[0]),
                int(row[3]),
                int(row[2]),
                float(row[6]),
                None,
            )


def import_weather_history_csv(
    csv_path: Path | str,
    db_path: Path | None = None,
    replace_existing: bool = True,
) -> int:
    target = initialize_weather_database(db_path)
    source = Path(csv_path)
    if not source.exists():
        raise FileNotFoundError(f"Nie znaleziono pliku CSV: {source}")

    lines = source.read_text(encoding="utf-8").splitlines()
    if not lines:
        return 0
    first_line = lines[0].strip().lower()
    has_header = first_line.startswith("temp,feels_like,pressure,humidity,lat,lon,pm10,download_timestamp")
    rows = list(_rows_from_header_csv(source) if has_header else _rows_from_legacy_csv(source))

    insert_sql = """
    INSERT INTO weather_history (
        observed_at,
        location,
        temperature_c,
        humidity,
        pressure_hpa,
        wind_speed_ms,
        weather_description
    )
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    with sqlite3.connect(target) as conn:
        if replace_existing:
            conn.execute("DELETE FROM weather_history")
        conn.executemany(insert_sql, rows)
        conn.commit()

    return len(rows)


@dataclass
class WeatherHistoryRecord:
    observed_at: datetime
    location: str
    temperature_c: float
    humidity: int | None = None
    pressure_hpa: int | None = None
    wind_speed_ms: float | None = None
    weather_description: str | None = None


class WeatherHistoryRepository:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or _db_path()

    def add_record(self, record: WeatherHistoryRecord) -> int:
        query = """
        INSERT INTO weather_history (
            observed_at,
            location,
            temperature_c,
            humidity,
            pressure_hpa,
            wind_speed_ms,
            weather_description
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                query,
                (
                    record.observed_at.isoformat(),
                    record.location,
                    record.temperature_c,
                    record.humidity,
                    record.pressure_hpa,
                    record.wind_speed_ms,
                    record.weather_description,
                ),
            )
            conn.commit()
        return int(cur.lastrowid)

    def get_records(self, limit: int = 100) -> list[dict]:
        query = """
        SELECT
            id,
            observed_at,
            location,
            temperature_c,
            humidity,
            pressure_hpa,
            wind_speed_ms,
            weather_description,
            created_at
        FROM weather_history
        ORDER BY observed_at DESC
        LIMIT ?
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(query, (limit,))
            return [dict(row) for row in cur.fetchall()]


if __name__ == "__main__":
    db_file = initialize_weather_database()
    print(
        "Utworzono (lub potwierdzono istnienie) bazy SQLite i tabeli weather_history: "
        f"{db_file}"
    )
