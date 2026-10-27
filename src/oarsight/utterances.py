"""Split turns into utterances, the unit of coding.

A single turn often mixes several ideas ("Sí. Y acerca de la metformina, ¿qué hace que se te olvide?"), and coding the
whole turn with one code loses information. Splitting is deterministic and never changes the words: each utterance
is an exact substring of its turn, so every later quote can be traced back to the transcript.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .roles import RoleAssignment
from .transcription import Transcript

# Break after sentence-ending punctuation, and before an opening ¿ or ¡ that follows other text.
_BREAK = re.compile(r"(?<=[.?!…])\s+|\s+(?=[¿¡])")
LONG_UTTERANCE_WORDS = 45


@dataclass
class Utterance:
    id: str
    turn: int
    speaker: str | None
    role: str
    start: float
    end: float
    text: str

    @property
    def is_long(self) -> bool:
        """Very long unpunctuated utterances may hide several behaviors; flagged for review."""
        return len(self.text.split()) > LONG_UTTERANCE_WORDS


def split_text(text: str) -> list[str]:
    return [part.strip() for part in _BREAK.split(text) if part and part.strip()]


def build_utterances(transcript: Transcript, roles: RoleAssignment) -> list[Utterance]:
    utterances: list[Utterance] = []
    for index, turn in enumerate(transcript.turns):
        for part in split_text(turn.text):
            utterances.append(
                Utterance(
                    id=f"U{len(utterances) + 1:03d}",
                    turn=index,
                    speaker=turn.speaker,
                    role=roles.role_of(turn.speaker),
                    start=turn.start,
                    end=turn.end,
                    text=part,
                )
            )
    return utterances


def save(utterances: list[Utterance], path: Path) -> None:
    path.write_text(json.dumps([asdict(u) for u in utterances], ensure_ascii=False, indent=2), encoding="utf-8")


def load(path: Path) -> list[Utterance]:
    return [Utterance(**u) for u in json.loads(path.read_text(encoding="utf-8"))]
