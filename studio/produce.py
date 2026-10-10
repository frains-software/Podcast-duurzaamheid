"""Van redactiescript naar afgemixte aflevering, inclusief meelees-transcript en golfvorm."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import numpy as np

from . import audio, config, jingle
from .elevenlabs import ElevenLabs, Speech
from .script import KIND_LABELS, Script, Segment, load, pronounce, split_sentences

INTRO_OVERLAP = 1.6  # de staart van de openingstune loopt onder de eerste woorden door
OUTRO_DELAY = 0.35  # korte adempauze tussen het laatste woord en de slottune


def produce(day: str, fake_voice: bool = False) -> dict:
    script = load(config.script_path(day))
    vcfg, acfg = config.voice(), config.audio()
    cache = config.BUILD / "tts" / day
    cache.mkdir(parents=True, exist_ok=True)

    if fake_voice:
        voice_id, voice_name, client = "fake", "testtoon", None
    else:
        client = ElevenLabs()
        voice_id, voice_name = client.resolve_voice(vcfg.get("voice_id", ""), vcfg.get("voice_name_hint", ""))
        print(f"• stem: {voice_name} ({voice_id}), model {vcfg['model_id']}")

    takes = []
    for i, seg in enumerate(script.segments):
        text = f"{vcfg.get('delivery_tag', '')} {seg.voiced}".strip()
        speech = _synthesise(client, cache, i, text, voice_id, vcfg) if client else _fake_speech(text)
        clip = audio.decode(speech.audio)
        clip, trimmed = audio.trim_silence(clip)
        takes.append((seg, text, speech, clip, trimmed))
        print(f"• {i + 1}/{len(script.segments)} {seg.kind:<7} {len(clip) / audio.SR:5.1f}s  {seg.label}")

    mix, chapters, transcript = _assemble(script, takes, acfg)

    out = config.BUILD / "audio" / f"{day}.mp3"
    audio.encode_mp3(mix, out, acfg["bitrate"], acfg["loudness_lufs"], acfg["true_peak"])
    show = config.show()
    audio.tag_mp3(out, script.title, show["host"], show["title"], day, config.ASSETS / "art" / "cover-1400.jpg")

    meta = _metadata(script, out, mix, chapters, transcript, vcfg["model_id"], voice_name, acfg)
    path = config.episode_path(day)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return meta


# ── stem ───────────────────────────────────────────────────────────────

def _synthesise(client: ElevenLabs, cache: Path, index: int, text: str, voice_id: str, vcfg: dict) -> Speech:
    """Synthetiseert één segment, met cache zodat een herhaalde run niet opnieuw tekens kost."""
    key = hashlib.sha256(
        json.dumps([text, voice_id, vcfg["model_id"], vcfg["stability"], vcfg["similarity_boost"]]).encode()
    ).hexdigest()[:16]
    mp3, align = cache / f"{index:02d}-{key}.mp3", cache / f"{index:02d}-{key}.json"
    if mp3.exists() and align.exists():
        data = json.loads(align.read_text())
        return Speech(mp3.read_bytes(), data.get("starts"), data.get("chars"))
    speech = client.speak(
        text,
        voice_id,
        vcfg["model_id"],
        vcfg["stability"],
        vcfg["similarity_boost"],
        vcfg.get("language_code", ""),
        vcfg.get("output_format", "mp3_44100_128"),
    )
    mp3.write_bytes(speech.audio)
    align.write_text(json.dumps({"starts": speech.char_starts, "chars": speech.characters}))
    return speech


def _fake_speech(text: str) -> Speech:
    """Testmodus: een zacht 'gemurmel' met de lengte die de tekst ongeveer zou hebben."""
    seconds = max(1.0, len(text.split()) / 2.4)
    t = np.arange(int(seconds * audio.SR)) / audio.SR
    syllables = 0.5 + 0.5 * np.sin(2 * np.pi * 4.2 * t) ** 2
    tone = np.sin(2 * np.pi * 140 * t) + 0.4 * np.sin(2 * np.pi * 280 * t)
    sig = (0.2 * tone * syllables).astype(np.float32)
    return Speech(audio.wav_bytes(np.stack([sig, sig], axis=1)), None, None)


# ── montage ────────────────────────────────────────────────────────────

def _assemble(script: Script, takes: list, acfg: dict) -> tuple[np.ndarray, list[dict], list[dict]]:
    gap = float(acfg.get("gap_seconds", 0.45))
    intro = audio.decode(jingle.clip_path("intro"))
    stinger = audio.decode(jingle.clip_path("stinger"))
    outro = audio.decode(jingle.clip_path("outro"))

    tl = audio.Timeline()
    tl.place(intro, 0.0)
    cursor = len(intro) / audio.SR - INTRO_OVERLAP
    chapters: list[dict] = []
    transcript: list[dict] = []

    for idx, (seg, text, speech, clip, trimmed) in enumerate(takes):
        prev = takes[idx - 1][0].kind if idx else None
        # Een tune vóór elk nieuwsbericht en vóór de duiding: de klassieke bulletin-structuur.
        if seg.kind in ("story", "insight") and prev is not None:
            tl.place(stinger, cursor)
            cursor += len(stinger) / audio.SR * 0.82
        start = tl.place(clip, cursor)
        length = len(clip) / audio.SR
        chapters.append(_chapter(seg, len(chapters), start))
        transcript.extend(_cues(seg, text, speech, start, length, trimmed, len(chapters) - 1))
        cursor = start + length + gap

    tl.place(outro, cursor - gap + OUTRO_DELAY)
    tl.pad(0.4)
    return tl.buf, chapters, transcript


def _chapter(seg: Segment, index: int, start: float) -> dict:
    return {
        "index": index,
        "kind": seg.kind,
        "kindLabel": KIND_LABELS[seg.kind],
        "title": seg.label,
        "start": round(start, 2),
        "sources": [s.to_dict() for s in seg.sources],
    }


def _cues(seg: Segment, text: str, speech: Speech, start: float, length: float, trimmed: float, chapter: int) -> list[dict]:
    """Zinnen met tijdcodes. Met ElevenLabs-uitlijning op het teken nauwkeurig, anders naar rato."""
    sentences = split_sentences(seg.spoken)
    if not sentences:
        return []
    times: list[float] = []
    aligned = speech.char_starts and speech.characters and len(speech.characters) == len(text)
    cursor = 0
    for sentence in sentences:
        # Het transcript toont de geschreven zin; de stem kreeg de fonetische versie.
        voiced = pronounce(sentence)
        pos = text.find(voiced, cursor)
        if pos < 0:
            aligned = False
            break
        cursor = pos + len(voiced)
        if aligned:
            times.append(max(0.0, speech.char_starts[pos] - trimmed))
    if not aligned or len(times) != len(sentences):
        total = sum(len(s) for s in sentences)
        acc, times = 0, []
        for s in sentences:
            times.append(length * acc / total)
            acc += len(s)
    cues = []
    for i, sentence in enumerate(sentences):
        s = start + times[i]
        e = start + (times[i + 1] if i + 1 < len(times) else length)
        cues.append({"start": round(s, 2), "end": round(e, 2), "text": sentence, "chapter": chapter})
    return cues


def _metadata(script: Script, mp3: Path, mix: np.ndarray, chapters, transcript, model, voice_name, acfg) -> dict:
    existing = sorted(p.stem for p in config.EPISODES.glob("*.json") if p.stem < script.date)
    pps = int(acfg.get("peaks_per_second", 12))
    return {
        "id": script.date,
        "number": len(existing) + 1,
        "date": script.date,
        "published": config.publish_datetime(date.fromisoformat(script.date)).isoformat(),
        "title": script.title,
        "summary": script.summary,
        "duration": round(audio.duration(mp3), 2),
        "size": mp3.stat().st_size,
        "audioFile": f"audio/{script.date}.mp3",
        "model": model,
        "voice": voice_name,
        "numberOfTheDay": script.number_of_the_day,
        "chapters": chapters,
        "transcript": transcript,
        "sources": [s.to_dict() for s in script.sources],
        "peaksPerSecond": pps,
        "peaks": audio.peaks(mix, pps),
    }
