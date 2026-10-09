"""Leest podcast.toml en levert paden en instellingen voor de hele studio."""

from __future__ import annotations

import tomllib
from datetime import date, datetime, time
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
REDACTIE = ROOT / "redactie"
EPISODES = ROOT / "episodes"
ASSETS = ROOT / "assets"
SITE_SRC = ROOT / "site"
BUILD = ROOT / "build"


@lru_cache(maxsize=1)
def load() -> dict:
    with open(ROOT / "podcast.toml", "rb") as fh:
        return tomllib.load(fh)


def show() -> dict:
    return load()["show"]


def voice() -> dict:
    return load()["voice"]


def audio() -> dict:
    return load()["audio"]


def schedule() -> dict:
    return load()["schedule"]


def tz() -> ZoneInfo:
    return ZoneInfo(schedule()["timezone"])


def now_local() -> datetime:
    return datetime.now(tz())


def today_local() -> date:
    return now_local().date()


def publish_datetime(day: date) -> datetime:
    hh, mm = (int(x) for x in schedule()["publish_time"].split(":"))
    return datetime.combine(day, time(hh, mm), tz())


def site_url() -> str:
    return show()["site_url"].rstrip("/")


def script_path(day: str) -> Path:
    return REDACTIE / f"{day}.json"


def episode_path(day: str) -> Path:
    return EPISODES / f"{day}.json"
