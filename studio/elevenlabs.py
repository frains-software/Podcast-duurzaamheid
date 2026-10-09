"""Dunne client voor de ElevenLabs Text to Speech API (Eleven v4 met gekloonde stem)."""

from __future__ import annotations

import base64
import os
import time
from dataclasses import dataclass

import requests

API = "https://api.elevenlabs.io"


class ElevenLabsError(RuntimeError):
    pass


@dataclass
class Speech:
    audio: bytes
    # Tijd (seconden) per teken in de verstuurde tekst; None als het model geen uitlijning teruggeeft.
    char_starts: list[float] | None
    characters: list[str] | None


class ElevenLabs:
    def __init__(self, api_key: str | None = None, timeout: float = 180.0):
        self.session = requests.Session()
        key = api_key or os.environ.get("ELEVENLABS_API_KEY")
        # Zonder key mag de aanroep toch doorgaan: in een Claude-cloudomgeving voegt de proxy hem toe.
        if key:
            self.session.headers["xi-api-key"] = key
        self.timeout = timeout

    # ── stem ────────────────────────────────────────────────────────────
    def resolve_voice(self, voice_id: str = "", name_hint: str = "") -> tuple[str, str]:
        """Geeft (voice_id, naam). Zonder voice_id zoeken we de gekloonde stem in het account."""
        voice_id = os.environ.get("ELEVENLABS_VOICE_ID") or voice_id
        if voice_id:
            return voice_id, voice_id
        resp = self._request("GET", "/v1/voices")
        voices = resp.json().get("voices", [])
        own = [v for v in voices if v.get("category") in ("professional", "cloned")]
        if not own:
            raise ElevenLabsError(
                "Geen gekloonde stem gevonden in dit ElevenLabs-account. "
                "Zet ELEVENLABS_VOICE_ID of voice.voice_id in podcast.toml."
            )
        hint = name_hint.lower()

        def rank(v: dict) -> tuple[int, int]:
            named = 0 if hint and hint in v.get("name", "").lower() else 1
            pro = 0 if v.get("category") == "professional" else 1
            return named, pro

        best = sorted(own, key=rank)[0]
        return best["voice_id"], best.get("name", best["voice_id"])

    # ── spraak ──────────────────────────────────────────────────────────
    def speak(
        self,
        text: str,
        voice_id: str,
        model_id: str,
        stability: float,
        similarity_boost: float,
        language_code: str = "",
        output_format: str = "mp3_44100_128",
    ) -> Speech:
        """Zet tekst om naar spraak. Probeert eerst mét tijdcodes (voor het meelees-transcript),
        en valt terug op gewone synthese als het model of het abonnement dat niet ondersteunt."""
        base = {
            "text": text,
            "model_id": model_id,
            "voice_settings": {"stability": stability, "similarity_boost": similarity_boost},
        }
        bodies = [dict(base, language_code=language_code), base] if language_code else [base]
        params = {"output_format": output_format}
        last_error: Exception | None = None
        for with_timestamps in (True, False):
            path = f"/v1/text-to-speech/{voice_id}" + ("/with-timestamps" if with_timestamps else "")
            for body in bodies:
                try:
                    resp = self._request("POST", path, json=body, params=params)
                except ElevenLabsError as exc:
                    if getattr(exc, "status", 0) in (400, 404, 422):
                        last_error = exc
                        continue
                    raise
                if not with_timestamps:
                    return Speech(resp.content, None, None)
                data = resp.json()
                align = data.get("alignment") or data.get("normalized_alignment") or {}
                return Speech(
                    base64.b64decode(data["audio_base64"]),
                    align.get("character_start_times_seconds"),
                    align.get("characters"),
                )
        raise ElevenLabsError(f"Spraaksynthese mislukt: {last_error}")

    # ── http ────────────────────────────────────────────────────────────
    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        delay = 2.0
        for attempt in range(6):
            resp = self.session.request(method, API + path, timeout=self.timeout, **kwargs)
            if resp.status_code < 400:
                return resp
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < 5:
                time.sleep(delay)
                delay *= 2
                continue
            err = ElevenLabsError(f"ElevenLabs {method} {path} gaf {resp.status_code}: {resp.text[:400]}")
            err.status = resp.status_code
            raise err
        raise AssertionError("onbereikbaar")
