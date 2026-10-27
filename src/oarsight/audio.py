"""Audio preparation with ffmpeg: WAV conversion, chunking, and speech estimation.

Voice Transcribe's file endpoint takes mono 16-bit PCM WAV at 16 or 24 kHz, up to 10 minutes per request.
Speech intervals (from ffmpeg's silencedetect) are the reference for the coverage check: they tell us how much
of the audio contained speech, independently of what the transcription model returned.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

SAMPLE_RATE = 24_000  # Voice Transcribe's native rate
MAX_CHUNK_SECONDS = 590.0  # stays under the 10-minute request limit
CHUNK_OVERLAP_SECONDS = 2.0


@dataclass(frozen=True)
class Interval:
    start: float
    end: float

    @property
    def length(self) -> float:
        return max(self.end - self.start, 0.0)


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=True)


def to_wav(source: Path, target: Path) -> Path:
    """Convert any audio file to mono 16-bit PCM WAV at 24 kHz, stripping metadata."""
    target.parent.mkdir(parents=True, exist_ok=True)
    _run(
        ["ffmpeg", "-loglevel", "error", "-y", "-i", str(source), "-ac", "1", "-ar", str(SAMPLE_RATE),
         "-c:a", "pcm_s16le", "-map_metadata", "-1", str(target)]
    )
    return target


def duration_seconds(path: Path) -> float:
    out = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)])
    return float(out.stdout.strip())


def plan_chunks(duration: float, max_len: float = MAX_CHUNK_SECONDS, overlap: float = CHUNK_OVERLAP_SECONDS) -> list[Interval]:
    """Split [0, duration] into windows of at most max_len seconds that overlap by `overlap` seconds."""
    if duration <= max_len:
        return [Interval(0.0, duration)]
    chunks: list[Interval] = []
    start = 0.0
    while True:
        end = min(start + max_len, duration)
        chunks.append(Interval(start, end))
        if end >= duration:
            return chunks
        start = end - overlap


def cut(wav: Path, interval: Interval, target: Path) -> Path:
    _run(
        ["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{interval.start:.3f}", "-t", f"{interval.length:.3f}",
         "-i", str(wav), "-c", "copy", str(target)]
    )
    return target


_SILENCE_START = re.compile(r"silence_start: (-?[\d.]+)")
_SILENCE_END = re.compile(r"silence_end: ([\d.]+)")


def parse_silencedetect(stderr: str, duration: float) -> list[Interval]:
    """Turn ffmpeg silencedetect output into the complementary list of speech (non-silent) intervals."""
    starts = [max(float(x), 0.0) for x in _SILENCE_START.findall(stderr)]
    ends = [float(x) for x in _SILENCE_END.findall(stderr)]
    if len(ends) < len(starts):  # silence that runs to the end of the file
        ends.append(duration)
    speech: list[Interval] = []
    cursor = 0.0
    for s, e in sorted(zip(starts, ends)):
        if s > cursor:
            speech.append(Interval(cursor, s))
        cursor = max(cursor, e)
    if cursor < duration:
        speech.append(Interval(cursor, duration))
    return [iv for iv in speech if iv.length > 0.05]


def speech_intervals(wav: Path, noise_db: int = -35, min_silence: float = 1.5) -> list[Interval]:
    """Intervals that contain sound above the noise floor (an estimate of where people were talking)."""
    result = subprocess.run(
        ["ffmpeg", "-i", str(wav), "-af", f"silencedetect=noise={noise_db}dB:d={min_silence}", "-f", "null", "-"],
        capture_output=True, text=True, check=True,
    )
    return parse_silencedetect(result.stderr, duration_seconds(wav))
