"""Procedureel gecomponeerde tunes voor Grondstof.

Geen samples en geen licenties: alles wordt hier met numpy gesynthetiseerd, zodat de
studio overal draait. Een warme FM-'Rhodes', een tikkende nieuwsklok, een zachte pad en
een klok-accent, samen in D-majeur. Wil je eigen muziek gebruiken, zet dan
`assets/audio/intro.mp3`, `stinger.mp3` en/of `outro.mp3` neer; die gaan voor.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from . import config
from .audio import SR, write_wav

BPM = 108
BEAT = 60 / BPM
EIGHTH = BEAT / 2
RNG = np.random.default_rng(1952)  # het oprichtingsjaar van De Graaf Groep


def hz(note: str) -> float:
    names = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}
    name, octave = note[:-1], int(note[-1])
    midi = 12 * (octave + 1) + names[name]
    return 440.0 * 2 ** ((midi - 69) / 12)


def _t(dur: float) -> np.ndarray:
    return np.arange(int(dur * SR)) / SR


def adsr(n: int, a: float, d: float, s: float, r: float) -> np.ndarray:
    a_n, d_n, r_n = int(a * SR), int(d * SR), int(r * SR)
    s_n = max(0, n - a_n - d_n - r_n)
    env = np.concatenate([
        np.linspace(0, 1, a_n, endpoint=False),
        np.linspace(1, s, d_n, endpoint=False),
        np.full(s_n, s),
        np.linspace(s, 0, r_n),
    ])
    return np.pad(env, (0, max(0, n - len(env))))[:n]


def rhodes(freq: float, dur: float, vel: float = 0.8) -> np.ndarray:
    """FM-elektrische piano: 1:1-modulatie met snel afnemende index en een tinehoogte."""
    t = _t(dur)
    index = (1.6 * vel) * np.exp(-t * 7.0) + 0.15
    mod = np.sin(2 * np.pi * freq * t)
    body = np.sin(2 * np.pi * freq * t + index * mod)
    tine = 0.18 * vel * np.sin(2 * np.pi * freq * 7.0 * t) * np.exp(-t * 28)
    env = np.exp(-t * (1.6 + freq / 900)) * (1 - np.exp(-t * 900))
    return (body + tine) * env * vel


def bell(freq: float, dur: float, vel: float = 0.6) -> np.ndarray:
    t = _t(dur)
    ratios = (1.0, 2.76, 5.4, 8.93)
    amps = (1.0, 0.45, 0.22, 0.1)
    decays = (1.4, 2.6, 4.5, 7.0)
    out = sum(a * np.sin(2 * np.pi * freq * r * t) * np.exp(-t * d) for r, a, d in zip(ratios, amps, decays))
    return out * (1 - np.exp(-t * 2000)) * vel


def pad(freqs: list[float], dur: float, attack: float = 1.2, release: float = 1.5, vel: float = 0.25) -> np.ndarray:
    t = _t(dur)
    out = np.zeros_like(t)
    for f in freqs:
        for detune in (-0.0035, 0.0, 0.0041):
            ph = RNG.uniform(0, 2 * np.pi)
            # Afgeronde zaagtand: een paar harmonischen, zacht gefilterd.
            out += sum(np.sin(2 * np.pi * f * (1 + detune) * k * t + ph * k) / k ** 1.6 for k in range(1, 6))
    out *= adsr(len(t), attack, 0.4, 0.85, release) / (len(freqs) * 3)
    return _lowpass(out, 1800) * vel


def sub(freq: float, dur: float, vel: float = 0.5) -> np.ndarray:
    t = _t(dur)
    return np.sin(2 * np.pi * freq * t) * np.exp(-t * 1.3) * (1 - np.exp(-t * 300)) * vel


def tick(vel: float = 0.25) -> np.ndarray:
    """De nieuwsklok: een kort, hoog getikt klikje."""
    t = _t(0.05)
    noise = RNG.standard_normal(len(t))
    noise = noise - _lowpass(noise, 3500)
    tone = np.sin(2 * np.pi * 2350 * t)
    return (0.6 * noise + 0.5 * tone) * np.exp(-t * 140) * vel


def swell(dur: float, vel: float = 0.18) -> np.ndarray:
    """Opzwellende, gefilterde ruis als aanloop naar een accent."""
    t = _t(dur)
    noise = RNG.standard_normal(len(t))
    shaped = _lowpass(noise, 2500) * (t / dur) ** 2.2
    return shaped * vel


def _lowpass(x: np.ndarray, cutoff: float) -> np.ndarray:
    spec = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(len(x), 1 / SR)
    spec *= 1 / np.sqrt(1 + (freqs / cutoff) ** 4)
    return np.fft.irfft(spec, n=len(x))


def reverb(stereo: np.ndarray, seconds: float = 2.4, mix: float = 0.28) -> np.ndarray:
    """Convolutiegalm met een synthetische, gedecorreleerde impulsrespons."""
    n_ir = int(seconds * SR)
    t = np.arange(n_ir) / SR
    out = np.zeros((len(stereo) + n_ir - 1, 2))
    for ch in range(2):
        ir = RNG.standard_normal(n_ir) * np.exp(-t * 6.9 / seconds)
        ir = _lowpass(ir, 6000)
        ir[: int(0.012 * SR)] = 0  # pre-delay
        ir /= np.sqrt((ir ** 2).sum())
        size = 1 << int(np.ceil(np.log2(len(out))))
        wet = np.fft.irfft(np.fft.rfft(stereo[:, ch], size) * np.fft.rfft(ir, size), size)[: len(out)]
        out[:, ch] = wet * mix
    out[: len(stereo)] += stereo * (1 - mix * 0.5)
    return out


class Mix:
    def __init__(self, dur: float):
        self.buf = np.zeros((int(dur * SR), 2))

    def add(self, sig: np.ndarray, at: float, pan: float = 0.0, gain: float = 1.0) -> None:
        start = int(at * SR)
        end = min(len(self.buf), start + len(sig))
        if end <= start:
            return
        left = np.cos((pan + 1) * np.pi / 4)
        right = np.sin((pan + 1) * np.pi / 4)
        seg = sig[: end - start] * gain
        self.buf[start:end, 0] += seg * left
        self.buf[start:end, 1] += seg * right

    def render(self, verb: float = 2.4, mix: float = 0.28, rms_db: float = -21.0, fade_out: float = 0.8) -> np.ndarray:
        wet = reverb(self.buf, verb, mix)
        # Kort de staart in tot een nette lengte en fade uit.
        tail = int(min(len(wet), len(self.buf) + 0.9 * SR))
        wet = wet[:tail]
        fade = int(fade_out * SR)
        wet[-fade:] *= np.linspace(1, 0, fade)[:, None] ** 2
        rms = np.sqrt((wet ** 2).mean()) or 1.0
        wet *= 10 ** (rms_db / 20) / rms
        peak = np.abs(wet).max()
        if peak > 0.89:
            wet *= 0.89 / peak
        return wet.astype(np.float32)


# ── composities ─────────────────────────────────────────────────────────

BM9 = ["B2", "D4", "F#4", "A4", "C#5"]
GMAJ7 = ["G2", "B3", "D4", "F#4", "A4"]
DMAJ9 = ["D3", "A3", "C#4", "E4", "F#4"]


def ident() -> np.ndarray:
    """Openingstune (~6 s): tikkende klok, Rhodes-arpeggio, en een warm slotakkoord."""
    m = Mix(6.2)
    bar = 4 * BEAT
    for i in range(16):  # twee maten tikken op de achtsten
        m.add(tick(0.28 if i % 2 == 0 else 0.16), i * EIGHTH, pan=0.35 if i % 2 else -0.35)
    pattern = [1, 2, 3, 4, 3, 2, 3, 4]
    for b, chord in enumerate((BM9, GMAJ7)):
        m.add(pad([hz(n) for n in chord[1:4]], bar + 0.4, attack=0.6, release=0.6, vel=0.22), b * bar)
        m.add(sub(hz(chord[0]), bar, 0.2), b * bar)
        for i, step in enumerate(pattern):
            note = chord[step]
            m.add(rhodes(hz(note), 1.2, 0.55 + 0.1 * (i % 2 == 0)), b * bar + i * EIGHTH, pan=(-0.4 + 0.1 * step))
    hit = 2 * bar
    m.add(swell(0.5), hit - 0.5)
    for n in DMAJ9:
        m.add(rhodes(hz(n), 2.6, 0.75), hit, pan=-0.2 + 0.1 * DMAJ9.index(n))
    m.add(pad([hz(n) for n in DMAJ9[1:]], 1.9, attack=0.05, release=1.4, vel=0.3), hit)
    m.add(sub(hz("D2"), 1.8, 0.32), hit)
    m.add(bell(hz("F#5"), 1.8, 0.35), hit, pan=0.3)
    m.add(bell(hz("A5"), 1.8, 0.22), hit + EIGHTH, pan=-0.3)
    return m.render()


def stinger() -> np.ndarray:
    """Korte overgang tussen berichten (~1,6 s)."""
    m = Mix(1.4)
    m.add(swell(0.35, 0.12), 0.0)
    m.add(tick(0.22), 0.35)
    m.add(rhodes(hz("A4"), 1.0, 0.5), 0.35, pan=-0.25)
    m.add(rhodes(hz("D5"), 1.0, 0.55), 0.35 + EIGHTH, pan=0.25)
    m.add(bell(hz("F#5"), 0.9, 0.15), 0.35 + EIGHTH)
    m.add(sub(hz("D2"), 0.8, 0.3), 0.35)
    return m.render(verb=1.6, mix=0.25, rms_db=-24.0, fade_out=0.5)


def outro() -> np.ndarray:
    """Slottune (~6 s): dalend arpeggio dat oplost op D."""
    m = Mix(6.0)
    bar = 4 * BEAT
    m.add(pad([hz(n) for n in GMAJ7[1:4]], bar + 0.3, attack=0.3, release=0.5, vel=0.2), 0)
    m.add(sub(hz("G2"), bar, 0.3), 0)
    for i, note in enumerate(reversed(GMAJ7[1:] + ["D5"])):
        m.add(rhodes(hz(note), 1.4, 0.55), i * EIGHTH * 1.5, pan=0.3 - 0.12 * i)
    for i in range(8):
        m.add(tick(0.12), bar - 2 * BEAT + i * EIGHTH * 0.5, pan=0.2)
    end = bar
    for n in DMAJ9:
        m.add(rhodes(hz(n), 3.0, 0.7), end)
    m.add(pad([hz(n) for n in DMAJ9[1:]], 2.8, attack=0.05, release=2.4, vel=0.28), end)
    m.add(sub(hz("D2"), 2.5, 0.3), end)
    m.add(bell(hz("D6"), 2.5, 0.25), end + BEAT)
    return m.render(verb=3.0, mix=0.32, rms_db=-22.5, fade_out=1.6)


def render_all() -> list[Path]:
    out_dir = config.ASSETS / "audio" / "generated"
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, fn in (("intro", ident), ("stinger", stinger), ("outro", outro)):
        path = out_dir / f"{name}.wav"
        write_wav(fn(), path)
        written.append(path)
    return written


def clip_path(name: str) -> Path:
    """Eigen muziek in assets/audio/ gaat voor op de gegenereerde tunes."""
    for ext in ("mp3", "wav", "m4a"):
        custom = config.ASSETS / "audio" / f"{name}.{ext}"
        if custom.exists():
            return custom
    generated = config.ASSETS / "audio" / "generated" / f"{name}.wav"
    if not generated.exists():
        render_all()
    return generated
