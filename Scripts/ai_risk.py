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
Dokonujesz oceny ryzyka dla wędrówki górskiej dla wskazanego punktu w Tatrach.
Ocenę wykonujesz na podstawie 24-godzinnej prognozy (prognozowana temperatura co 3 godziny).
W odpowiedzi wskazujesz swoją ocenę poziomu ryzyka oraz krótkie uzasadnienie.
""".strip()


class RiskAssessment(BaseModel):
    recommendation: str = Field(description="Wartość z listy: safe, risky, dangerous")
    justification: str = Field(description="Krótkie uzasadnienie rekomendacji")


def assess_risk(forecast_24h: dict) -> RiskAssessment:
    """
    Ocenia ryzyko wędrówki górskiej na podstawie 24-godzinnej prognozy temperatury.

    Args:
        forecast_24h: Słownik {czas: temperatura} — 8 odczytów co 3 godziny (24h).

    Returns:
        RiskAssessment z polem recommendation (safe/risky/dangerous) i justification.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("Brak klucza OPENROUTER_API_KEY w pliku .env")

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    messages = [
        {"role": "system", "content": SYSTEM_MESSAGE},
        {"role": "user", "content": json.dumps(forecast_24h, ensure_ascii=False)},
    ]

    response = client.responses.parse(
        model=MODEL,
        input=messages,
        text_format=RiskAssessment,
    )
    return response.output_parsed
