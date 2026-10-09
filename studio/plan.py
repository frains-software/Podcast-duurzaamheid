"""Bepaalt wat een run van de studio-workflow moet doen.

- push:      de redactie (Claude-routine of een mens) heeft een script gepusht → produceren.
- schedule:  vangnet na negen uur: is er vandaag nog niets, dan zelf schrijven en produceren.
- dispatch:  handmatig starten, eventueel voor een andere datum of geforceerd opnieuw.
"""

from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta

from . import config

SAFETY_MARGIN = timedelta(minutes=20)


def decide(event: str, requested_date: str = "", force: str = "false", changed: str = "", now: datetime | None = None) -> dict:
    now = now or config.now_local()
    forced = str(force).lower() in ("1", "true", "yes")

    if event == "push":
        days = sorted({m for m in re.findall(r"redactie/(\d{4}-\d{2}-\d{2})\.json", changed)}, reverse=True)
        for day in days:
            if config.script_path(day).exists() and (forced or not config.episode_path(day).exists()):
                return _result(day, "produce", "nieuw script van de redactie")
        return _result(days[0] if days else now.date().isoformat(), "skip", "geen nieuw script om te produceren")

    day = date.fromisoformat(requested_date).isoformat() if requested_date else now.date().isoformat()
    has_episode = config.episode_path(day).exists()
    has_script = config.script_path(day).exists()

    if event == "schedule":
        deadline = config.publish_datetime(now.date()) + SAFETY_MARGIN
        if now < deadline:
            return _result(day, "skip", f"te vroeg: vangnet start pas na {deadline:%H:%M}")
        if has_episode:
            return _result(day, "skip", "aflevering van vandaag staat al klaar")

    elif has_episode and not forced:
        return _result(day, "skip", "aflevering bestaat al (gebruik force om opnieuw te maken)")

    if has_script:
        return _result(day, "produce", "script aanwezig")
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _result(day, "write", "geen script: Claude schrijft zelf een bulletin")
    return _result(day, "skip", "geen script en geen ANTHROPIC_API_KEY voor de terugvaloptie")


def _result(day: str, action: str, reason: str) -> dict:
    return {"date": day, "action": action, "reason": reason}
