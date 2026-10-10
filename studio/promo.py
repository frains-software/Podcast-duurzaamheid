"""Promovideo's voor social media: jouw stem, meelopende ondertiteling en de Grondstof-look.

    python -m studio promo-voice promo/linkedin-lancering.json   # inspreken (ElevenLabs)
    python -m studio promo-video promo/linkedin-lancering.json   # renderen naar MP4

De stem wordt gecachet in build/promo/<naam>/, zodat opnieuw renderen niets kost.
"""

from __future__ import annotations

import difflib
import json
import math
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import art, audio, config, jingle
from .elevenlabs import ElevenLabs
from .script import pronounce

VOICE_START = 1.8      # seconden muziek vóór de eerste woorden
END_CARD = 6.2         # lengte van de eindkaart na het laatste woord
FONTS = config.ASSETS / "fonts"

NIGHT, AUBERGINE, VIOLET, ORCHID = art.NIGHT, art.AUBERGINE, art.VIOLET, art.ORCHID
EMBER, AMBER, CREAM = art.EMBER, art.AMBER, art.CREAM


# ── gegevens ────────────────────────────────────────────────────────────

@dataclass
class Word:
    text: str
    start: float
    end: float
    sentence: int


def load_spec(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def workdir(spec: dict) -> Path:
    d = config.BUILD / "promo" / spec["name"]
    d.mkdir(parents=True, exist_ok=True)
    return d


def full_text(spec: dict) -> str:
    return " ".join(s["text"] for s in spec["sentences"])


# ── stem ────────────────────────────────────────────────────────────────

def voice(spec_path: Path, fake: bool = False) -> Path:
    spec = load_spec(spec_path)
    out = workdir(spec)
    text = pronounce(full_text(spec))
    mp3, align = out / "voice.mp3", out / "alignment.json"
    if fake:
        seconds = len(text.split()) / 2.4
        t = np.arange(int(seconds * audio.SR)) / audio.SR
        sig = (0.2 * np.sin(2 * np.pi * 140 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 4.2 * t) ** 2)).astype(np.float32)
        audio.write_wav(np.stack([sig, sig], 1), out / "voice.wav")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(out / "voice.wav"), str(mp3)], check=True)
        align.write_text(json.dumps({"text": text, "chars": None, "starts": None}))
        return mp3
    vcfg = config.voice()
    client = ElevenLabs()
    voice_id, name = client.resolve_voice(vcfg.get("voice_id", ""), vcfg.get("voice_name_hint", ""))
    print(f"• stem: {name}, model {vcfg['model_id']}, {len(text)} tekens")
    speech = client.speak(text, voice_id, vcfg["model_id"], vcfg["stability"], vcfg["similarity_boost"],
                          vcfg.get("language_code", ""), vcfg.get("output_format", "mp3_44100_128"))
    mp3.write_bytes(speech.audio)
    align.write_text(json.dumps({"text": text, "chars": speech.characters, "starts": speech.char_starts}))
    print(f"• uitlijning per teken: {'ja' if speech.char_starts else 'nee'}")
    return mp3


def word_timings(spec: dict, voice_len: float, trimmed: float, align: dict) -> list[Word]:
    """Tijd per getoond woord. Gebruikt de ElevenLabs-uitlijning (of words.json) en koppelt die aan de
    geschreven tekst, ook waar de stem een fonetische versie kreeg (Wastenet → Weestnet)."""
    display: list[tuple[str, int]] = []
    for i, s in enumerate(spec["sentences"]):
        display += [(w, i) for w in s["text"].split()]

    override = workdir(spec) / "words.json"
    voiced: list[tuple[str, float]] = []
    if override.exists():
        voiced = [(w["word"], w["start"] - trimmed) for w in json.loads(override.read_text())]
    elif align.get("starts") and align.get("chars"):
        text, starts = "".join(align["chars"]), align["starts"]
        for m in re.finditer(r"\S+", text):
            voiced.append((m.group(), starts[m.start()] - trimmed))

    def norm(w: str) -> str:
        return re.sub(r"[^\wà-ÿ]", "", w.lower())

    times: list[float | None] = [None] * len(display)
    if voiced:
        sm = difflib.SequenceMatcher(a=[norm(w) for w, _ in display], b=[norm(w) for w, _ in voiced], autojunk=False)
        for tag, a0, a1, b0, b1 in sm.get_opcodes():
            if tag == "equal":
                for k in range(a1 - a0):
                    times[a0 + k] = voiced[b0 + k][1]
            elif tag == "replace" and b1 > b0:
                t0 = voiced[b0][1]
                t1 = voiced[b1][1] if b1 < len(voiced) else voice_len
                for k in range(a1 - a0):
                    times[a0 + k] = t0 + (t1 - t0) * k / (a1 - a0)
    if any(t is None for t in times):
        # Naar rato van het aantal tekens, verankerd aan de bekende tijden.
        total = sum(len(w) + 1 for w, _ in display)
        acc = 0
        for k, (w, _) in enumerate(display):
            if times[k] is None:
                times[k] = voice_len * acc / total
            acc += len(w) + 1
    words = []
    for k, (w, s) in enumerate(display):
        start = max(0.0, times[k])
        end = times[k + 1] if k + 1 < len(display) else voice_len
        words.append(Word(w, start + VOICE_START, max(start + 0.12, end) + VOICE_START, s))
    return words


# ── muziek ──────────────────────────────────────────────────────────────

def music_bed(seconds: float) -> np.ndarray:
    """Zacht bed onder de stem: warme pad in de Grondstof-akkoorden met een tikkende nieuwsklok."""
    m = jingle.Mix(seconds + 1)
    bar = 4 * jingle.BEAT
    chords = [jingle.BM9, jingle.GMAJ7, jingle.DMAJ9, jingle.GMAJ7]
    n_bars = int(seconds / bar) + 1
    for b in range(n_bars):
        chord = chords[b % len(chords)]
        m.add(jingle.pad([jingle.hz(n) for n in chord[1:4]], bar + 0.6, attack=0.8, release=0.8, vel=0.22), b * bar)
        m.add(jingle.sub(jingle.hz(chord[0]), bar, 0.18), b * bar)
        for i in range(8):
            m.add(jingle.tick(0.10 if i % 2 else 0.16), b * bar + i * jingle.EIGHTH, pan=0.3 if i % 2 else -0.3)
        if b % 2 == 0:
            m.add(jingle.rhodes(jingle.hz(chord[3]), 1.6, 0.28), b * bar + 2 * jingle.BEAT, pan=0.2)
    bed = m.render(verb=2.0, mix=0.25, rms_db=-31.0, fade_out=1.5)
    n = int(seconds * audio.SR)
    bed = np.pad(bed, ((0, max(0, n - len(bed))), (0, 0)))[:n]
    fade = int(1.2 * audio.SR)
    bed[:fade] *= np.linspace(0, 1, fade)[:, None]
    return bed


def build_audio(spec: dict) -> tuple[np.ndarray, float, float, float]:
    """Geeft (mix, stemduur, weggeknipte stilte, totale duur)."""
    out = workdir(spec)
    voice_clip, trimmed = audio.trim_silence(audio.decode(out / "voice.mp3"))
    voice_len = len(voice_clip) / audio.SR
    total = VOICE_START + voice_len + END_CARD
    tl = audio.Timeline()
    tl.place(music_bed(VOICE_START + voice_len + 1.0), 0.0)
    tl.place(audio.decode(jingle.clip_path("stinger")), 0.15, gain_db=-2)
    tl.place(voice_clip, VOICE_START, gain_db=2)
    tl.place(audio.decode(jingle.clip_path("outro")), VOICE_START + voice_len + 0.35)
    mix = tl.buf[: int(total * audio.SR)]
    if len(mix) < int(total * audio.SR):
        mix = np.pad(mix, ((0, int(total * audio.SR) - len(mix)), (0, 0)))
    return mix, voice_len, trimmed, total


def envelope(mix: np.ndarray, fps: int, seconds: float) -> np.ndarray:
    """Energie per frame (0…1), voor de animaties."""
    hop = audio.SR // fps
    n = int(seconds * fps)
    mono = np.abs(mix.mean(axis=1))
    frames = np.array([np.sqrt(np.mean(mono[i * hop:(i + 1) * hop] ** 2)) if i * hop < len(mono) else 0 for i in range(n)])
    ref = np.percentile(frames, 97) or 1
    env = np.clip(frames / ref, 0, 1) ** 0.7
    smooth = np.convolve(env, np.ones(3) / 3, mode="same")
    return smooth


# ── beeld ───────────────────────────────────────────────────────────────

def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


def ease(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 3


class Painter:
    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self.small = (w // 8, h // 8)
        rng = np.random.default_rng(7)
        self.grain = [rng.normal(0, 6, (h, w, 1)).astype(np.int16) for _ in range(6)]
        sy, sx = np.mgrid[0:self.small[1], 0:self.small[0]]
        self.gx, self.gy = sx / self.small[0], sy / self.small[1] * (h / w)
        self.f_title = _font("fraunces-latin-600-normal.woff2", 92)
        self.f_kicker = _font("fraunces-latin-600-normal.woff2", 78)
        self.f_italic = _font("fraunces-latin-600-italic.woff2", 36)
        self.f_sub = _font("Inter-SemiBold.otf", 46)
        self.f_eyebrow = _font("Inter-SemiBold.otf", 24)
        self.f_small = _font("Inter-Medium.otf", 28)
        self.f_cta = _font("Inter-SemiBold.otf", 40)
        self.f_core = _font("Inter-SemiBold.otf", 34)
        cover = Image.open(config.ASSETS / "art" / "cover-1400.jpg").convert("RGB")
        self.cover = cover.resize((620, 620), Image.Resampling.LANCZOS)
        self.cover_mask = Image.new("L", (620, 620), 0)
        ImageDraw.Draw(self.cover_mask).rounded_rectangle((0, 0, 619, 619), radius=44, fill=255)

    def background(self, t: float, energy: float) -> Image.Image:
        ar = self.h / self.w
        blobs = [
            (0.20 + 0.08 * math.sin(t * 0.21), 0.18 + 0.06 * math.cos(t * 0.17), 0.62, VIOLET, 0.95),
            (0.88 + 0.05 * math.sin(t * 0.13 + 1), 0.30 + 0.07 * math.sin(t * 0.19), 0.42, ORCHID, 0.5 + 0.15 * energy),
            (0.92 + 0.05 * math.cos(t * 0.15), ar * 0.92 + 0.05 * math.sin(t * 0.23), 0.70, EMBER, 0.9 + 0.1 * energy),
            (0.55 + 0.10 * math.sin(t * 0.11 + 2), ar * 0.70, 0.35, AMBER, 0.35 + 0.25 * energy),
            (0.05, ar * 0.95, 0.55, AUBERGINE, 0.9),
        ]
        img = np.zeros((self.small[1], self.small[0], 3)) + np.array(NIGHT, float)
        for cx, cy, r, color, strength in blobs:
            d = np.sqrt((self.gx - cx) ** 2 + (self.gy - cy) ** 2)
            wgt = np.exp(-(d / r) ** 2 * 2.2) * min(1.0, strength)
            img = img * (1 - wgt[..., None]) + np.array(color, float) * wgt[..., None]
        base = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).resize((self.w, self.h), Image.Resampling.BICUBIC)
        arr = np.asarray(base, np.int16) + self.grain[int(t * 12) % len(self.grain)]
        return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGBA")

    def visualizer(self, size: int, t: float, energy: float, levels: list[float], reveal: float) -> Image.Image:
        s = size * 2
        layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        c = s / 2
        ring = s * 0.29
        arc_r = s * 0.43
        spin = t * 0.35
        # golfvormring
        n = len(levels)
        for i, v in enumerate(levels):
            a = i / n * 2 * math.pi - math.pi / 2 + spin * 0.25
            inner, outer = ring, ring + s * 0.10 * max(0.06, v) * reveal + 3
            warm = i / n
            col = (255, int(107 + 74 * warm), int(26 + 45 * warm), int(255 * (0.35 + 0.65 * v) * reveal))
            d.line([(c + math.cos(a) * inner, c + math.sin(a) * inner), (c + math.cos(a) * outer, c + math.sin(a) * outer)],
                   fill=col, width=max(4, int(s * 0.009)))
        # drie pijlen
        lw = int(s * 0.024)
        for k in range(3):
            start = k * 120 + 12 + math.degrees(spin)
            sweep = 92 * reveal
            end = start + sweep
            box = (c - arc_r - lw / 2, c - arc_r - lw / 2, c + arc_r + lw / 2, c + arc_r + lw / 2)
            colr = AMBER if k == 0 else CREAM
            d.arc(box, start, end, fill=colr + (240,), width=lw)
            if reveal > 0.05:
                a1, tip = math.radians(end), math.radians(end + 7)
                px, py = c + arc_r * math.cos(a1), c + arc_r * math.sin(a1)
                tx, ty = c + arc_r * math.cos(tip), c + arc_r * math.sin(tip)
                nx, ny, hd = math.cos(a1), math.sin(a1), lw * 1.7
                d.polygon([(px + nx * hd, py + ny * hd), (tx, ty), (px - nx * hd, py - ny * hd)], fill=colr + (255,))
        # deeltjes
        for i in range(26):
            r = s * 0.5 * (0.62 + 0.36 * ((i * 37) % 100) / 100)
            a = t * (0.08 + (i % 7) * 0.025) * (0.4 + 1.6 * energy) + i * 0.97
            pr = 2 + i % 4
            x, y = c + math.cos(a) * r, c + math.sin(a) * r
            d.ellipse((x - pr, y - pr, x + pr, y + pr), fill=CREAM + (int(255 * (0.25 + 0.5 * energy) * reveal),))
        img = layer.resize((size, size), Image.Resampling.LANCZOS)
        # gloeiende kern
        core = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        cd = ImageDraw.Draw(core)
        cr = size * (0.15 + 0.05 * energy) * reveal
        cd.ellipse((size / 2 - cr, size / 2 - cr, size / 2 + cr, size / 2 + cr), fill=EMBER + (int(200 * reveal),))
        core = core.filter(ImageFilter.GaussianBlur(size * 0.05))
        cd2 = ImageDraw.Draw(core)
        cr2 = size * 0.105 * reveal
        cd2.ellipse((size / 2 - cr2, size / 2 - cr2, size / 2 + cr2, size / 2 + cr2), fill=AMBER + (int(235 * reveal),))
        core.alpha_composite(img)
        if reveal > 0.3:
            cd3 = ImageDraw.Draw(core)
            label = "09:00"
            tw = cd3.textlength(label, font=self.f_core)
            cd3.text(((size - tw) / 2, size / 2 - self.f_core.size * 0.62), label, font=self.f_core,
                     fill=NIGHT + (int(235 * min(1, (reveal - 0.3) / 0.4)),))
        return core

    def text_center(self, d: ImageDraw.ImageDraw, y: float, text: str, font, fill, spacing: int = 6) -> None:
        for line in text.split("\n"):
            w = d.textlength(line, font=font)
            d.text(((self.w - w) / 2, y), line, font=font, fill=fill)
            y += font.size + spacing

    def tracked(self, d: ImageDraw.ImageDraw, y: float, text: str, font, fill, tracking: float) -> None:
        widths = [font.getlength(ch) for ch in text]
        x = (self.w - (sum(widths) + tracking * (len(text) - 1))) / 2
        for ch, w in zip(text, widths):
            d.text((x, y), ch, font=font, fill=fill)
            x += w + tracking


def caption_chunks(words: list[Word], max_chars: int = 30, max_lines: int = 2) -> list[list[list[int]]]:
    """Groepeert woorden in ondertitelblokken van maximaal twee regels, nooit over een zin heen."""
    chunks, lines, line, length = [], [], [], 0
    for i, w in enumerate(words):
        new_sentence = line and words[line[-1]].sentence != w.sentence
        if line and (length + 1 + len(w.text) > max_chars or new_sentence):
            lines.append(line)
            line, length = [], 0
            if len(lines) == max_lines or new_sentence:
                chunks.append(lines)
                lines = []
        line.append(i)
        length += len(w.text) + (1 if length else 0)
        if w.text.endswith((".", "?", "!")) and len(lines) + 1 >= max_lines:
            lines.append(line)
            chunks.append(lines)
            lines, line, length = [], [], 0
    if line:
        lines.append(line)
    if lines:
        chunks.append(lines)
    return chunks


def render(spec_path: Path, out_path: Path | None = None) -> Path:
    spec = load_spec(spec_path)
    wd = workdir(spec)
    W, H, FPS = spec["format"]["width"], spec["format"]["height"], spec["format"]["fps"]
    mix, voice_len, trimmed, total = build_audio(spec)
    align = json.loads((wd / "alignment.json").read_text())
    words = word_timings(spec, voice_len, trimmed, align)
    env = envelope(mix, FPS, total)
    chunks = caption_chunks(words)
    sentence_start = {}
    for w in words:
        sentence_start.setdefault(w.sentence, w.start)
    voice_end = VOICE_START + voice_len

    wav = wd / "mix.wav"
    audio.write_wav(mix * (10 ** (-1.0 / 20)), wav)
    out_path = out_path or config.ROOT / "build" / "promo" / f"{spec['name']}.mp4"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    srt = out_path.with_suffix(".srt")
    srt.write_text(_srt(words, chunks), encoding="utf-8")

    p = Painter(W, H)
    ff = subprocess.Popen([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-i", str(wav),
        "-af", "loudnorm=I=-14:TP=-1.0:LRA=11",
        "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-profile:v", "high",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest", "-movflags", "+faststart",
        str(out_path),
    ], stdin=subprocess.PIPE)

    n_frames = int(total * FPS)
    peaks_per_frame = env
    for f in range(n_frames):
        t = f / FPS
        e = float(env[min(f, len(env) - 1)])
        end_mix = ease((t - voice_end - 0.2) / 0.8)
        frame = p.background(t, e)
        d = ImageDraw.Draw(frame)

        # bovenbalk
        top_alpha = int(255 * ease(t / 0.8) * (1 - end_mix))
        if top_alpha:
            p.tracked(d, 64, "GRONDSTOF  ·  ELKE OCHTEND 09:00", p.f_eyebrow, AMBER + (top_alpha,), 5)

        # visualizer
        if end_mix < 1:
            lo = max(0, f - 42)
            window = list(peaks_per_frame[lo:f + 42]) or [0.1]
            levels = [float(window[int(i / 84 * len(window))]) for i in range(84)]
            viz = p.visualizer(640, t, e, levels, ease(t / 1.4))
            if end_mix > 0:
                viz.putalpha(viz.getchannel("A").point(lambda a, m=end_mix: int(a * (1 - m))))
            frame.alpha_composite(viz, ((W - 640) // 2, 120))

        # titel tijdens de intro, daarna de kicker van de huidige zin
        if t < VOICE_START + 0.4:
            a = ease(t / 0.9) * (1 - ease((t - VOICE_START) / 0.4))
            p.text_center(d, 800, "Grondstof", p.f_title, CREAM + (int(255 * a),))
            p.text_center(d, 910, "het circulaire ochtendbulletin", p.f_italic, AMBER + (int(230 * a),))
        elif end_mix < 1:
            current = max((s for s, st in sentence_start.items() if st <= t + 0.15), default=0)
            age = t - sentence_start.get(current, 0) + 0.15
            a = ease(age / 0.45) * (1 - end_mix)
            dy = (1 - ease(age / 0.45)) * 40
            kicker = spec["sentences"][current].get("kicker", "")
            lines = kicker.count("\n") + 1
            y0 = 800 + dy - (lines - 1) * 20
            p.text_center(d, y0, kicker, p.f_kicker, CREAM + (int(255 * a),), spacing=10)

        # ondertiteling
        if VOICE_START - 0.1 <= t <= voice_end + 0.3:
            _draw_caption(p, frame, words, chunks, t)

        # eindkaart
        if end_mix > 0:
            _end_card(p, frame, spec, t - voice_end, end_mix)

        # onderregel
        d2 = ImageDraw.Draw(frame)
        p.text_center(d2, H - 70, "met Frans van den Berge  ·  De Graaf Groep", p.f_small,
                      CREAM + (int(170 * ease(t / 1.2)),))

        ff.stdin.write(frame.convert("RGB").tobytes())
        if f % (FPS * 10) == 0:
            print(f"• frame {f}/{n_frames}")
    ff.stdin.close()
    ff.wait()
    if ff.returncode:
        raise RuntimeError("ffmpeg kon de video niet maken")
    print(f"✓ {out_path.relative_to(config.ROOT)} ({total:.1f} s) + {srt.name}")
    return out_path


def _draw_caption(p: Painter, frame: Image.Image, words: list[Word], chunks, t: float) -> None:
    current = None
    for ch in chunks:
        first, last = words[ch[0][0]], words[ch[-1][-1]]
        if first.start - 0.05 <= t:
            current = ch
        if t < last.end:
            break
    if current is None:
        return
    first = words[current[0][0]]
    a = ease((t - first.start + 0.05) / 0.18)
    active = max((i for line in current for i in line if words[i].start <= t), default=-1)
    line_h = p.f_sub.size + 14
    box_h = line_h * len(current) + 40
    widths = [sum(p.f_sub.getlength(words[i].text + " ") for i in line) for line in current]
    box_w = max(widths) + 60
    y_top = p.h - 330
    overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle(((p.w - box_w) / 2, y_top, (p.w + box_w) / 2, y_top + box_h), radius=28,
                         fill=NIGHT + (int(165 * a),))
    for li, line in enumerate(current):
        x = (p.w - widths[li]) / 2
        y = y_top + 20 + li * line_h
        for i in line:
            w = words[i]
            spoken = w.start <= t
            now = i == active and t < w.end + 0.25
            colr = AMBER if now else CREAM
            alpha = int(255 * a) if spoken else int(120 * a)
            od.text((x, y), w.text, font=p.f_sub, fill=colr + (alpha,))
            x += p.f_sub.getlength(w.text + " ")
    frame.alpha_composite(overlay)


def _end_card(p: Painter, frame: Image.Image, spec: dict, since: float, mix: float) -> None:
    layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    scale = 0.92 + 0.08 * ease(since / 1.2)
    size = int(620 * scale)
    cover = p.cover.resize((size, size), Image.Resampling.LANCZOS)
    mask = p.cover_mask.resize((size, size), Image.Resampling.LANCZOS)
    glow = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    cx, cy = p.w // 2, 150 + 310
    gd.rounded_rectangle((cx - size / 2 - 10, cy - size / 2 - 10, cx + size / 2 + 10, cy + size / 2 + 10), radius=60,
                         fill=EMBER + (110,))
    glow = glow.filter(ImageFilter.GaussianBlur(40))
    layer.alpha_composite(glow)
    layer.paste(cover, (cx - size // 2, cy - size // 2), mask)
    cta = spec["cta"]
    ca = ease((since - 0.5) / 0.6)
    bw = p.f_cta.getlength(cta["title"]) + 90
    by = 830
    d.rounded_rectangle(((p.w - bw) / 2, by, (p.w + bw) / 2, by + 86), radius=43, fill=AMBER + (int(255 * ca),))
    p.text_center(d, by + 19, cta["title"], p.f_cta, NIGHT + (int(255 * ca),))
    la = ease((since - 0.9) / 0.6)
    p.text_center(d, 960, "\n".join(cta["lines"]), p.f_small, CREAM + (int(230 * la),), spacing=16)
    layer.putalpha(layer.getchannel("A").point(lambda a: int(a * mix)))
    frame.alpha_composite(layer)


def _srt(words: list[Word], chunks) -> str:
    def ts(x: float) -> str:
        ms = int(round(x * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"

    out = []
    for n, ch in enumerate(chunks, 1):
        start, end = words[ch[0][0]].start, words[ch[-1][-1]].end
        text = "\n".join(" ".join(words[i].text for i in line) for line in ch)
        out.append(f"{n}\n{ts(start)} --> {ts(end)}\n{text}\n")
    return "\n".join(out)
