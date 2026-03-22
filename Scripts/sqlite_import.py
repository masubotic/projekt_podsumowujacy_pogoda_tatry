from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from weather_db import import_weather_history_csv, initialize_weather_database

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import danych pogodowych z CSV do bazy SQLite."
    )
    parser.add_argument(
        "--csv",
        default=str(PROJECT_ROOT / "data" / "weather_history.csv"),
        help="Sciezka do pliku CSV z danymi pogodowymi.",
    )
    parser.add_argument(
        "--db",
        default=str(PROJECT_ROOT / "data" / "weather.db"),
        help="Sciezka do pliku bazy SQLite.",
    )
    parser.add_argument(
        "--mode",
        choices=["replace", "append"],
        default="replace",
        help="Tryb importu: replace (usun stare i wstaw nowe) lub append (dopisz).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    csv_path = Path(args.csv).resolve()
    db_path = Path(args.db).resolve()
    replace_existing = args.mode == "replace"

    initialize_weather_database(db_path)
    inserted = import_weather_history_csv(
        csv_path=csv_path,
        db_path=db_path,
        replace_existing=replace_existing,
    )

    with sqlite3.connect(db_path) as conn:
        total = conn.execute("SELECT COUNT(*) FROM weather_history").fetchone()[0]

    print(f"CSV: {csv_path}")
    print(f"DB: {db_path}")
    print(f"Tryb: {args.mode}")
    print(f"Zaimportowano: {inserted}")
    print(f"Liczba rekordow w tabeli: {total}")


if __name__ == "__main__":
    main()
