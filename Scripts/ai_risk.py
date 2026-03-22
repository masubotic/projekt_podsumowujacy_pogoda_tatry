from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

MODEL = "anthropic/claude-sonnet-4-6"

SYSTEM_MESSAGE = """
Jesteś ekspertem oceny ryzyka wędrówek górskich w Tatrach.

Otrzymujesz listę punktów geograficznych pokrywających obszar Tatr wraz z 24-godzinną
prognozą temperatury dla każdego z nich (odczyty co 3 godziny).
Użytkownik opisuje słownie lokalizację, którą go interesuje.

Twoje zadanie:
1. Na podstawie opisu użytkownika dopasuj punkt z listy, który najlepiej pasuje do opisu.
2. Oceń ryzyko wędrówki górskiej dla tego punktu na podstawie jego prognozy temperatury.

Kontekst geograficzny siatki punktów (lat/lon):
- Zakres siatki: lat 49.17–49.31, lon 19.76–20.13
- Zachodnia część (lon ~19.76–19.87): okolice Zakopanego, Dolina Kościeliska, Chochołowska
- Środek zachodni (lon ~19.88–19.99): Kasprowy Wierch ok. lat=49.23, lon=19.98
- Środek wschodni (lon ~20.00–20.07): Dolina Pięciu Stawów, okolice Morskiego Oka
- Wschodnia część (lon ~20.08–20.13): Rysy i granica słowacka
- Wyższe partie (niższe lat ~49.17–49.22): główne grzbiety i szczyty
- Niższe partie / doliny (wyższe lat ~49.25–49.31): podtatrzańskie doliny po stronie polskiej

Zwróć współrzędne matched_lat i matched_lon dokładnie takie, jakie widnieją na liście punktów.

Zasady dotyczące pola justification:
- Pisz wyłącznie o warunkach pogodowych i ryzyku wędrówki — jakby użytkownik zapytał o pogodę w tym miejscu.
- NIE wspominaj o współrzędnych, wartościach lat/lon, punktach siatki ani procesie ich doboru.
- NIE wyjaśniaj, skąd wziąłeś dane ani jak dobrałeś punkt — po prostu oceń warunki i ryzyko.
""".strip()


class RiskAssessment(BaseModel):
    matched_lat: float = Field(
        description="Szerokość geograficzna dopasowanego punktu — dokładnie z listy"
    )
    matched_lon: float = Field(
        description="Długość geograficzna dopasowanego punktu — dokładnie z listy"
    )
    matched_description: str = Field(
        description="Krótki opis lokalizacji dopasowanego punktu (np. 'okolice Kasprowego Wierchu')"
    )
    recommendation: str = Field(
        description="Poziom ryzyka: safe, risky lub dangerous"
    )
    justification: str = Field(
        description="Uzasadnienie oceny ryzyka dla dopasowanego punktu"
    )


def assess_risk(all_points: list[dict], user_description: str) -> RiskAssessment:
    """
    Ocenia ryzyko wędrówki górskiej na podstawie opisu lokalizacji i prognoz wszystkich punktów.

    Args:
        all_points: Lista słowników {lat, lon, prognoza_24h} dla wszystkich punktów siatki.
        user_description: Słowny opis lokalizacji podany przez użytkownika.

    Returns:
        RiskAssessment z dopasowanym punktem i oceną ryzyka.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("Brak klucza OPENROUTER_API_KEY w pliku .env")

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    user_content = json.dumps(
        {"opis_lokalizacji": user_description, "punkty": all_points},
        ensure_ascii=False,
    )

    messages = [
        {"role": "system", "content": SYSTEM_MESSAGE},
        {"role": "user", "content": user_content},
    ]

    response = client.responses.parse(
        model=MODEL,
        input=messages,
        text_format=RiskAssessment,
    )
    return response.output_parsed
