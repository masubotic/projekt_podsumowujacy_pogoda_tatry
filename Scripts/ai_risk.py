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
Użytkownik opisuje lokalizację lub trasę wędrówki.

Twoje zadanie:
1. Oceń, czy opisana lokalizacja/trasa leży w Tatrach (siatka: lat 49.17–49.31, lon 19.76–20.13).
   Jeśli nie — ustaw in_tatry=False i zostaw matched_points jako pustą listę.

2. Jeśli lokalizacja/trasa jest w Tatrach:
   - Dla pojedynczego punktu lub miejsca: dopasuj 1 punkt z listy.
   - Dla trasy (np. "z Zakopanego na Kasprowy", "przez Dolinę Pięciu Stawów na Rysy",
     "pętla przez Czerwone Wierchy"): dopasuj kilka punktów reprezentujących kolejne
     etapy trasy, w logicznej kolejności od startu do mety.
   - Zwróć matched_lat i matched_lon dokładnie takie, jakie widnieją na liście punktów.

3. Dokonaj oceny ryzyka:
   - Dla trasy: uwzględnij warunki we wszystkich dopasowanych punktach.
     Recommendation = najgorszy poziom ryzyka spośród wszystkich punktów trasy.
   - Dla punktu: oceń na podstawie jego prognozy.

Kontekst geograficzny siatki:
- Zachodnia część (lon ~19.76–19.87): okolice Zakopanego, Dolina Kościeliska, Chochołowska
- Środek zachodni (lon ~19.88–19.99): Kasprowy Wierch ok. lat=49.23, lon=19.98
- Środek wschodni (lon ~20.00–20.07): Dolina Pięciu Stawów, Morskie Oko
- Wschodnia część (lon ~20.08–20.13): Rysy i granica słowacka
- Wyższe partie (niższe lat ~49.17–49.22): główne grzbiety i szczyty
- Niższe partie / doliny (wyższe lat ~49.25–49.31): podtatrzańskie doliny

Zasady dotyczące pola justification:
- Pisz wyłącznie o warunkach pogodowych i ryzyku wędrówki.
- Dla trasy wspomnij o warunkach w kluczowych jej punktach.
- NIE wspominaj o współrzędnych, wartościach lat/lon ani procesie doboru punktów.
""".strip()


class MatchedPoint(BaseModel):
    lat: float = Field(description="Szerokość geograficzna — dokładnie z listy punktów")
    lon: float = Field(description="Długość geograficzna — dokładnie z listy punktów")
    description: str = Field(description="Krótki opis tego punktu (np. 'Kasprowy Wierch', 'dolina startowa')")


class RiskAssessment(BaseModel):
    in_tatry: bool = Field(
        description="True jeśli lokalizacja/trasa jest w Tatrach, False jeśli poza obszarem siatki"
    )
    matched_points: list[MatchedPoint] = Field(
        default_factory=list,
        description="Lista dopasowanych punktów — jeden dla lokalizacji, kilka w kolejności dla trasy"
    )
    recommendation: str = Field(
        default="",
        description="Łączny poziom ryzyka: safe, risky lub dangerous"
    )
    justification: str = Field(
        default="",
        description="Uzasadnienie łącznej oceny ryzyka"
    )


def assess_risk(all_points: list[dict], user_description: str) -> RiskAssessment:
    """
    Ocenia ryzyko wędrówki dla lokalizacji lub trasy w Tatrach.

    Args:
        all_points: Lista {lat, lon, prognoza_24h} dla wszystkich punktów siatki.
        user_description: Opis lokalizacji lub trasy podany przez użytkownika.

    Returns:
        RiskAssessment z listą dopasowanych punktów i oceną ryzyka.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("Brak klucza OPENROUTER_API_KEY w pliku .env")

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    user_content = json.dumps(
        {"opis": user_description, "punkty": all_points},
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
