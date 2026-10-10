"""Het redactiescript: inlezen, valideren en voorbereiden voor de stem."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

KINDS = ("intro", "story", "insight", "number", "outro")
KIND_LABELS = {
    "intro": "Opening",
    "story": "Nieuws",
    "insight": "Duiding",
    "number": "Cijfer van de dag",
    "outro": "Afsluiting",
}

# Gemeten op de pilot met de stemkloon (Eleven v4): 726 woorden gaven 5:27 inclusief tunes.
WORDS_PER_SECOND = 2.4
MUSIC_SECONDS = 24  # opening, overgangen en slottune
TARGET_SECONDS = (285, 320)
HARD_SECONDS = (220, 420)

TAG_RE = re.compile(r"\[[^\]]{1,40}\]")
DIGIT_RE = re.compile(r"\d")
ABBREVIATION_RE = re.compile(r"\b[A-Z]{3,}\b")
FORBIDDEN_CHARS = set("()/*#_<>{}|~^`")
# Afkortingen die een stem prima uitspreekt.
SPEAKABLE = {"CBS", "NOS", "RIVM", "PBL", "MKB", "ANWB", "KNMI", "VNG", "NAVO", "VNO", "NCW", "TNO", "ABN", "AMRO", "ING", "KLM", "BTW"}


@dataclass
class Source:
    publisher: str
    title: str
    url: str

    def to_dict(self) -> dict:
        return {"publisher": self.publisher, "title": self.title, "url": self.url}


@dataclass
class Segment:
    kind: str
    text: str
    headline: str = ""
    sources: list[Source] = field(default_factory=list)

    @property
    def spoken(self) -> str:
        """Gesproken tekst zoals hij in het transcript staat (zonder eventuele audio-tags)."""
        return normalise(TAG_RE.sub("", self.text))

    @property
    def voiced(self) -> str:
        """Tekst zoals hij naar de stem gaat: met de uitspraaklijst uit podcast.toml toegepast."""
        return pronounce(self.spoken)

    @property
    def label(self) -> str:
        return self.headline or KIND_LABELS[self.kind]

    @property
    def words(self) -> int:
        return len(self.spoken.split())


@dataclass
class Script:
    date: str
    title: str
    summary: str
    segments: list[Segment]
    number_of_the_day: dict | None = None
    path: Path | None = None

    @property
    def words(self) -> int:
        return sum(s.words for s in self.segments)

    @property
    def estimated_seconds(self) -> float:
        """Geschatte lengte van de complete aflevering, inclusief tunes."""
        return self.words / WORDS_PER_SECOND + MUSIC_SECONDS

    @property
    def sources(self) -> list[Source]:
        seen, out = set(), []
        for seg in self.segments:
            for src in seg.sources:
                if src.url not in seen:
                    seen.add(src.url)
                    out.append(src)
        nod = self.number_of_the_day or {}
        src = nod.get("source")
        if isinstance(src, dict) and src.get("url") and src["url"] not in seen:
            out.append(Source(src.get("publisher", ""), src.get("title", ""), src["url"]))
        return out


class ScriptError(Exception):
    def __init__(self, errors: list[str], warnings: list[str]):
        super().__init__("\n".join(errors))
        self.errors = errors
        self.warnings = warnings


def pronounce(text: str) -> str:
    """Vervangt namen door hun fonetische schrijfwijze ([pronunciation] in podcast.toml)."""
    from . import config

    for written, spoken in config.load().get("pronunciation", {}).items():
        text = re.sub(rf"(?<!\w){re.escape(written)}(?!\w)", spoken, text)
    return text


def normalise(text: str) -> str:
    text = text.replace(" ", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def load(path: Path) -> Script:
    data = json.loads(path.read_text(encoding="utf-8"))
    script, errors, warnings = parse(data, expected_date=path.stem)
    if errors:
        raise ScriptError(errors, warnings)
    script.path = path
    return script


def parse(data: dict, expected_date: str | None = None) -> tuple[Script | None, list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    def need(obj: dict, key: str, where: str) -> str:
        val = obj.get(key)
        if not isinstance(val, str) or not val.strip():
            errors.append(f"{where}: veld '{key}' ontbreekt of is leeg")
            return ""
        return val.strip()

    if not isinstance(data, dict):
        return None, ["Het script moet een JSON-object zijn"], []

    day = need(data, "date", "script")
    if day:
        try:
            date.fromisoformat(day)
        except ValueError:
            errors.append(f"script: datum '{day}' is geen geldige JJJJ-MM-DD")
        if expected_date and day != expected_date:
            errors.append(f"script: datum '{day}' komt niet overeen met bestandsnaam '{expected_date}'")
    title = need(data, "title", "script")
    summary = need(data, "summary", "script")
    if len(title) > 90:
        warnings.append(f"titel is {len(title)} tekens (advies: max. 70)")
    if len(summary) > 360:
        warnings.append(f"samenvatting is {len(summary)} tekens (advies: max. 300)")

    segments: list[Segment] = []
    raw_segments = data.get("segments")
    if not isinstance(raw_segments, list) or not raw_segments:
        errors.append("script: 'segments' moet een niet-lege lijst zijn")
        raw_segments = []

    for i, raw in enumerate(raw_segments, 1):
        where = f"segment {i}"
        if not isinstance(raw, dict):
            errors.append(f"{where}: moet een object zijn")
            continue
        kind = raw.get("kind")
        if kind not in KINDS:
            errors.append(f"{where}: onbekend kind '{kind}' (kies uit {', '.join(KINDS)})")
            continue
        text = need(raw, "text", f"{where} ({kind})")
        headline = (raw.get("headline") or "").strip()
        sources = []
        for j, s in enumerate(raw.get("sources") or [], 1):
            if not isinstance(s, dict) or not str(s.get("url", "")).startswith(("http://", "https://")):
                errors.append(f"{where}: bron {j} heeft geen geldige url")
                continue
            sources.append(Source(str(s.get("publisher", "")).strip(), str(s.get("title", "")).strip(), s["url"].strip()))
        if kind == "story":
            if not headline:
                errors.append(f"{where}: een nieuwsbericht heeft een 'headline' nodig")
            if not sources:
                errors.append(f"{where}: een nieuwsbericht heeft minstens één bron nodig")
        if len(headline) > 100:
            warnings.append(f"{where}: kop is {len(headline)} tekens (advies: max. 80)")
        seg = Segment(kind=kind, text=text, headline=headline, sources=sources)
        segments.append(seg)
        _lint_spoken(seg, where, warnings, errors)

    kinds = [s.kind for s in segments]
    if segments:
        if kinds[0] != "intro":
            errors.append("het eerste segment moet 'intro' zijn")
        if kinds[-1] != "outro":
            errors.append("het laatste segment moet 'outro' zijn")
    stories = kinds.count("story")
    if stories < 3:
        errors.append(f"minstens drie nieuwsberichten nodig (nu {stories})")
    elif stories > 5:
        warnings.append(f"{stories} nieuwsberichten: dat past lastig in vijf minuten")
    if "insight" not in kinds:
        warnings.append("geen duiding ('insight') gevonden")

    nod = data.get("number_of_the_day")
    if nod is not None:
        if not isinstance(nod, dict) or not nod.get("value") or not nod.get("label"):
            errors.append("number_of_the_day: 'value' en 'label' zijn verplicht")
            nod = None

    script = Script(date=day, title=title, summary=summary, segments=segments, number_of_the_day=nod)
    secs = script.estimated_seconds
    if segments:
        if not HARD_SECONDS[0] <= secs <= HARD_SECONDS[1]:
            errors.append(
                f"geschatte duur {fmt_duration(secs)} ({script.words} woorden) valt buiten "
                f"{fmt_duration(HARD_SECONDS[0])}–{fmt_duration(HARD_SECONDS[1])}"
            )
        elif not TARGET_SECONDS[0] <= secs <= TARGET_SECONDS[1]:
            warnings.append(
                f"geschatte duur {fmt_duration(secs)} ({script.words} woorden); doel is "
                f"{fmt_duration(TARGET_SECONDS[0])}–{fmt_duration(TARGET_SECONDS[1])}"
            )
    return script, errors, warnings


def _lint_spoken(seg: Segment, where: str, warnings: list[str], errors: list[str]) -> None:
    text = seg.text
    if TAG_RE.search(text):
        warnings.append(f"{where}: bevat audio-tags; de studio verwijdert ze")
    digits = DIGIT_RE.findall(TAG_RE.sub("", text).replace("CO2", ""))
    if digits:
        warnings.append(f"{where}: bevat cijfers; schrijf getallen voluit voor de stem")
    if "http" in text or "www." in text:
        errors.append(f"{where}: bevat een URL in de gesproken tekst")
    bad = sorted(FORBIDDEN_CHARS.intersection(TAG_RE.sub("", text)))
    if bad:
        warnings.append(f"{where}: bevat tekens die slecht klinken: {' '.join(bad)}")
    abbreviations = sorted({a for a in ABBREVIATION_RE.findall(text) if a not in SPEAKABLE})
    if abbreviations:
        warnings.append(f"{where}: afkortingen om uit te schrijven: {', '.join(abbreviations)}")
    for sentence in re.split(r"(?<=[.!?])\s+", seg.spoken):
        if len(sentence.split()) > 30:
            warnings.append(f"{where}: lange zin ({len(sentence.split())} woorden): '{sentence[:60]}…'")


def fmt_duration(seconds: float) -> str:
    seconds = int(round(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def split_sentences(text: str) -> list[str]:
    """Knipt gesproken tekst in zinnen voor het meelees-transcript."""
    parts = re.split(r"(?<=[.!?…])\s+(?=[A-ZÀ-Ý\"'‘“0-9])", normalise(text))
    return [p for p in (x.strip() for x in parts) if p]
