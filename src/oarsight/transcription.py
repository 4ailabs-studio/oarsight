"""Transcription with Muse Voice Transcribe (file endpoint, DIARIZATION mode).

The transcript text always comes from the speech-recognition model, never from a language model: later stages
may label speakers or flag terms, but they never rewrite what was said.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from . import audio
from .api import TranscribeClient
from .audio import CHUNK_OVERLAP_SECONDS, Interval


@dataclass
class Turn:
    start: float
    end: float
    text: str
    speaker: str | None  # chunk-scoped label, e.g. "c0:A" (labels are not comparable across chunks)
    chunk: int


@dataclass
class Transcript:
    source: str
    duration: float
    turns: list[Turn]
    speech: list[Interval] = field(default_factory=list)
    chunks: list[Interval] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, text: str) -> Transcript:
        raw = json.loads(text)
        return cls(
            source=raw["source"],
            duration=raw["duration"],
            turns=[Turn(**t) for t in raw["turns"]],
            speech=[Interval(**i) for i in raw.get("speech", [])],
            chunks=[Interval(**i) for i in raw.get("chunks", [])],
        )


def turns_from_response(data: dict[str, Any], chunk_index: int, offset: float) -> list[Turn]:
    """Convert a /asr/transcribe response into turns on the global timeline, dropping empty turns."""
    turns = []
    for t in data.get("turns") or []:
        text = (t.get("transcript") or "").strip()
        if not text:
            continue
        speaker = t.get("speaker")
        turns.append(
            Turn(
                start=round(offset + t["startMs"] / 1000, 3),
                end=round(offset + t["endMs"] / 1000, 3),
                text=text,
                speaker=f"c{chunk_index}:{speaker}" if speaker else None,
                chunk=chunk_index,
            )
        )
    return turns


def merge_chunks(per_chunk: list[list[Turn]], chunks: list[Interval], overlap: float = CHUNK_OVERLAP_SECONDS) -> list[Turn]:
    """Merge chunk transcripts, keeping each turn from exactly one chunk around the overlaps."""
    boundaries = [chunks[k].start + overlap / 2 for k in range(1, len(chunks))]
    merged: list[Turn] = []
    for k, turns in enumerate(per_chunk):
        low = boundaries[k - 1] if k > 0 else float("-inf")
        high = boundaries[k] if k < len(boundaries) else float("inf")
        merged.extend(t for t in turns if low <= t.start < high)
    return sorted(merged, key=lambda t: t.start)


def transcribe_file(
    source: Path,
    client: TranscribeClient,
    workdir: Path,
    *,
    language_bias: list[str] | None = None,
    keywords: list[str] | None = None,
) -> Transcript:
    """Convert, chunk, transcribe and merge an audio file into a single transcript."""
    workdir.mkdir(parents=True, exist_ok=True)
    wav = audio.to_wav(source, workdir / "audio.wav")
    duration = audio.duration_seconds(wav)
    chunks = audio.plan_chunks(duration)
    per_chunk: list[list[Turn]] = []
    for k, chunk in enumerate(chunks):
        piece = wav if len(chunks) == 1 else audio.cut(wav, chunk, workdir / f"chunk_{k:02d}.wav")
        data = client.transcribe(piece, language_bias=language_bias or ["Spanish"], keywords=keywords)
        per_chunk.append(turns_from_response(data, k, chunk.start))
    return Transcript(
        source=source.name,
        duration=round(duration, 3),
        turns=merge_chunks(per_chunk, chunks),
        speech=audio.speech_intervals(wav),
        chunks=chunks,
    )
