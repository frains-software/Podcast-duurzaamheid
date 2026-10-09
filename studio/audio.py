"""Audiobewerking: decoderen, mixen op een tijdlijn, loudness-normalisatie en golfvorm-pieken."""

from __future__ import annotations

import io
import json
import re
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np

SR = 44100


def _ffmpeg(*args: str, input_bytes: bytes | None = None) -> subprocess.CompletedProcess:
    cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-y", *args]
    return subprocess.run(cmd, input=input_bytes, capture_output=True, check=True)


def decode(source: Path | bytes) -> np.ndarray:
    """Decodeert willekeurige audio naar float32 stereo (n, 2) op 44,1 kHz."""
    if isinstance(source, (bytes, bytearray)):
        proc = _ffmpeg("-i", "pipe:0", "-f", "f32le", "-ac", "2", "-ar", str(SR), "pipe:1", input_bytes=bytes(source))
    else:
        proc = _ffmpeg("-i", str(source), "-f", "f32le", "-ac", "2", "-ar", str(SR), "pipe:1")
    return np.frombuffer(proc.stdout, dtype=np.float32).reshape(-1, 2).copy()


def write_wav(samples: np.ndarray, path: Path) -> None:
    data = np.clip(samples, -1.0, 1.0)
    pcm = (data * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(pcm.shape[1] if pcm.ndim == 2 else 1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm.tobytes())


def trim_silence(samples: np.ndarray, threshold_db: float = -45.0, keep: float = 0.06) -> tuple[np.ndarray, float]:
    """Knipt stilte aan begin en eind weg. Geeft (geknipte audio, weggeknipte seconden aan het begin)."""
    mono = np.abs(samples).max(axis=1)
    hop = int(SR * 0.01)
    if len(mono) < hop:
        return samples, 0.0
    frames = mono[: len(mono) // hop * hop].reshape(-1, hop).max(axis=1)
    thresh = 10 ** (threshold_db / 20)
    loud = np.nonzero(frames > thresh)[0]
    if len(loud) == 0:
        return samples, 0.0
    start = max(0, loud[0] * hop - int(keep * SR))
    end = min(len(samples), (loud[-1] + 1) * hop + int(keep * SR))
    return samples[start:end], start / SR


class Timeline:
    """Eenvoudige multitrack: clips op een tijdstip plaatsen en optellen."""

    def __init__(self) -> None:
        self.buf = np.zeros((0, 2), dtype=np.float32)

    @property
    def end(self) -> float:
        return len(self.buf) / SR

    def place(self, clip: np.ndarray, at: float, gain_db: float = 0.0) -> float:
        start = int(round(at * SR))
        need = start + len(clip)
        if need > len(self.buf):
            self.buf = np.concatenate([self.buf, np.zeros((need - len(self.buf), 2), dtype=np.float32)])
        self.buf[start:need] += clip * (10 ** (gain_db / 20))
        return start / SR

    def pad(self, seconds: float) -> None:
        self.place(np.zeros((int(seconds * SR), 2), dtype=np.float32), self.end)


def encode_mp3(samples: np.ndarray, out: Path, bitrate: str, lufs: float, true_peak: float) -> None:
    """Tweetraps EBU R128-normalisatie (podcaststandaard −16 LUFS) en MP3-codering."""
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "mix.wav"
        write_wav(samples, wav)
        probe = _ffmpeg(
            "-i", str(wav),
            "-af", f"loudnorm=I={lufs}:TP={true_peak}:LRA=11:print_format=json",
            "-f", "null", "-",
        )
        stats = json.loads(re.findall(r"\{[^{}]+\}", probe.stderr.decode())[-1])
        filt = (
            f"loudnorm=I={lufs}:TP={true_peak}:LRA=11"
            f":measured_I={stats['input_i']}:measured_TP={stats['input_tp']}"
            f":measured_LRA={stats['input_lra']}:measured_thresh={stats['input_thresh']}"
            f":offset={stats['target_offset']}:linear=true"
        )
        _ffmpeg(
            "-i", str(wav), "-af", filt, "-ar", str(SR), "-ac", "2",
            "-codec:a", "libmp3lame", "-b:a", bitrate,
            "-id3v2_version", "3",
            str(out),
        )


def tag_mp3(path: Path, title: str, artist: str, album: str, date: str, cover: Path | None) -> None:
    """Zet ID3-tags en de cover in het MP3-bestand (zonder opnieuw te coderen)."""
    tmp = path.with_suffix(".tagged.mp3")
    args = ["-i", str(path)]
    if cover and cover.exists():
        args += ["-i", str(cover), "-map", "0:a", "-map", "1:v", "-c:v", "mjpeg", "-disposition:v", "attached_pic",
                 "-metadata:s:v", "title=Cover", "-metadata:s:v", "comment=Cover (front)"]
    else:
        args += ["-map", "0:a"]
    args += [
        "-c:a", "copy", "-id3v2_version", "3",
        "-metadata", f"title={title}", "-metadata", f"artist={artist}",
        "-metadata", f"album={album}", "-metadata", f"date={date}", "-metadata", "genre=Podcast",
        str(tmp),
    ]
    _ffmpeg(*args)
    tmp.replace(path)


def duration(path: Path) -> float:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, check=True, text=True,
    )
    return float(proc.stdout.strip())


def peaks(samples: np.ndarray, per_second: int) -> list[float]:
    """Golfvorm voor de app: RMS-energie per venster, geschaald naar 0…1."""
    mono = samples.mean(axis=1)
    hop = SR // per_second
    n = len(mono) // hop
    if n == 0:
        return []
    frames = mono[: n * hop].reshape(n, hop)
    rms = np.sqrt((frames ** 2).mean(axis=1))
    ref = np.percentile(rms, 98) or 1.0
    scaled = np.clip(rms / ref, 0, 1) ** 0.6
    return [round(float(x), 3) for x in scaled]


def wav_bytes(samples: np.ndarray) -> bytes:
    buf = io.BytesIO()
    data = (np.clip(samples, -1, 1) * 32767).astype("<i2")
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(data.tobytes())
    return buf.getvalue()
