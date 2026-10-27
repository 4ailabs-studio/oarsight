"""Coverage check: did the transcription capture the speech that is actually in the audio?

In an early real-world test, a different speech-to-text service silently dropped most of a 10-minute consultation.
Feedback built on such a transcript would be wrong without anyone noticing, so Oarsight refuses to analyze a
session whose transcript does not cover enough of the detected speech.
"""

from __future__ import annotations

from dataclasses import dataclass

from .audio import Interval
from .transcription import Transcript

MIN_COVERED_FRACTION = 0.80
MIN_GAP_SECONDS = 20.0
TURN_PADDING_SECONDS = 1.0


def union(intervals: list[Interval]) -> list[Interval]:
    merged: list[Interval] = []
    for iv in sorted(intervals, key=lambda i: i.start):
        if merged and iv.start <= merged[-1].end:
            merged[-1] = Interval(merged[-1].start, max(merged[-1].end, iv.end))
        else:
            merged.append(iv)
    return merged


def subtract(base: list[Interval], remove: list[Interval]) -> list[Interval]:
    """Parts of `base` not covered by `remove`."""
    remove = union(remove)
    result: list[Interval] = []
    for iv in union(base):
        cursor = iv.start
        for r in remove:
            if r.end <= cursor or r.start >= iv.end:
                continue
            if r.start > cursor:
                result.append(Interval(cursor, r.start))
            cursor = max(cursor, r.end)
        if cursor < iv.end:
            result.append(Interval(cursor, iv.end))
    return result


@dataclass
class Coverage:
    duration: float
    speech_seconds: float
    covered_speech_seconds: float
    fraction: float
    words: int
    words_per_speech_minute: float
    gaps: list[Interval]
    complete: bool


def assess(
    transcript: Transcript,
    min_fraction: float = MIN_COVERED_FRACTION,
    min_gap: float = MIN_GAP_SECONDS,
    padding: float = TURN_PADDING_SECONDS,
) -> Coverage:
    speech = union(transcript.speech) or [Interval(0.0, transcript.duration)]
    turns = [Interval(t.start - padding, t.end + padding) for t in transcript.turns]
    uncovered = subtract(speech, turns)
    speech_seconds = sum(iv.length for iv in speech)
    covered = speech_seconds - sum(iv.length for iv in uncovered)
    fraction = covered / speech_seconds if speech_seconds else 0.0
    # Join uncovered pieces separated by short pauses before measuring gap length.
    joined = union([Interval(iv.start, iv.end + 2.0) for iv in uncovered])
    gaps = [Interval(iv.start, iv.end - 2.0) for iv in joined if iv.length - 2.0 >= min_gap]
    words = sum(len(t.text.split()) for t in transcript.turns)
    return Coverage(
        duration=transcript.duration,
        speech_seconds=round(speech_seconds, 1),
        covered_speech_seconds=round(covered, 1),
        fraction=round(fraction, 3),
        words=words,
        words_per_speech_minute=round(words / (speech_seconds / 60), 1) if speech_seconds else 0.0,
        gaps=gaps,
        complete=fraction >= min_fraction and not gaps,
    )
