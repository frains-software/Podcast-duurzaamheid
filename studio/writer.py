"""Terugvaloptie: Claude schrijft zelf het bulletin via de Claude API (met webzoeken).

Normaal schrijft de dagelijkse Claude-routine het script. Lukt dat een keer niet, dan
springt de geplande GitHub Action hiermee in, zodat er om negen uur altijd een aflevering is.
Vereist het geheim ANTHROPIC_API_KEY.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import anthropic

from . import config
from .script import parse

MODEL = "claude-opus-5-5"
WEEKDAYS = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
MONTHS = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus",
          "september", "oktober", "november", "december"]
TOOLS = [
    {
        "type": "web_search_20260209",
        "name": "web_search",
        "max_uses": 14,
        "user_location": {"type": "approximate", "country": "NL", "timezone": "Europe/Amsterdam"},
    },
    {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 10},
]


def _recent_headlines(day: str, n: int = 7) -> str:
    lines = []
    for path in sorted(config.REDACTIE.glob("*.json"), reverse=True):
        if path.stem >= day or len(lines) >= n:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        heads = [s.get("headline", "") for s in data.get("segments", []) if s.get("kind") == "story"]
        lines.append(f"- {path.stem}: " + " | ".join(heads))
    return "\n".join(lines) or "- (nog geen eerdere afleveringen)"


def _extract_json(text: str) -> dict:
    fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    candidate = fenced[-1] if fenced else text[text.find("{"): text.rfind("}") + 1]
    return json.loads(candidate)


def write_script(day: str) -> Path:
    d = date.fromisoformat(day)
    spoken_date = f"{WEEKDAYS[d.weekday()]} {d.day} {MONTHS[d.month - 1]}"
    statute = (config.REDACTIE / "REDACTIESTATUUT.md").read_text(encoding="utf-8")
    wishes_path = config.REDACTIE / "REDACTIEWENSEN.md"
    if wishes_path.exists():
        statute += "\n\n" + wishes_path.read_text(encoding="utf-8")
    system = (
        "Je bent de eindredacteur van het dagelijkse podcastbulletin Grondstof. Volg het redactiestatuut "
        "hieronder strikt. Doe eerst gedegen nieuwsonderzoek met de zoek- en ophaaltools en gebruik alleen "
        "feiten die je in een bron hebt gelezen. Antwoord aan het eind met precies één JSON-codeblok volgens "
        "sectie 5 van het statuut, en verder niets.\n\n" + statute
    )
    prompt = (
        f"Schrijf de aflevering voor {spoken_date} {d.year} (bestandsdatum {day}). "
        f"Noem de dag in de intro als '{spoken_date}'.\n\n"
        f"Koppen van de vorige afleveringen (niet herhalen):\n{_recent_headlines(day)}"
    )

    client = anthropic.Anthropic()
    messages: list[dict] = [{"role": "user", "content": prompt}]
    for attempt in range(3):
        response, messages = _run(client, system, messages)
        text = "".join(b.text for b in response.content if b.type == "text")
        try:
            data = _extract_json(text)
            _, errors, _ = parse(data, expected_date=day)
        except (json.JSONDecodeError, ValueError) as exc:
            errors = [f"geen geldige JSON: {exc}"]
        if not errors:
            path = config.script_path(day)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return path
        print(f"! poging {attempt + 1}: {len(errors)} fouten, Claude verbetert het script")
        messages += [
            {"role": "assistant", "content": response.content},
            {"role": "user", "content": "De validator vond deze fouten:\n- " + "\n- ".join(errors)
             + "\nLever het volledige, verbeterde JSON-codeblok."},
        ]
    raise RuntimeError("Claude kon geen geldig script leveren")


def _run(client: anthropic.Anthropic, system: str, messages: list[dict]):
    """Eén beurt, inclusief hervatten na pause_turn (lange serverside zoekloops).
    Geeft het antwoord en de berichtenlijst inclusief eventuele gepauzeerde beurten."""
    for _ in range(6):
        with client.beta.messages.stream(
            model=MODEL,
            max_tokens=32000,
            system=system,
            messages=messages,
            tools=TOOLS,
            output_config={"effort": "high"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        ) as stream:
            response = stream.get_final_message()
        if response.stop_reason == "refusal":
            raise RuntimeError(f"Claude weigerde het verzoek: {response.stop_details}")
        if response.stop_reason != "pause_turn":
            return response, messages
        messages = messages + [{"role": "assistant", "content": response.content}]
    raise RuntimeError("te veel pause_turn-hervattingen")
