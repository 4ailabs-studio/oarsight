"""Key-moment candidates, generated in code (stage 8).

A candidate pairs a significant patient utterance (change talk, an emotion or
need, or strong sustain talk) with the clinician's next response. The
supervisor chooses among these candidates; it cannot invent moments.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .coding import Coding
from .utterances import Utterance

MAX_CANDIDATES = 8
SIGNIFICANT_PATIENT_CODES = frozenset({"CHANGE", "SUSTAIN"})
WEAK_RESPONSE_CODES = frozenset({"QUESTION", "PERSUADE", "CONFRONT"})
STRONG_RESPONSE_CODES = frozenset({"SIMPLE_REFLECTION", "COMPLEX_REFLECTION", "EMPHASIZE_AUTONOMY"})


@dataclass
class Candidate:
    id: str
    patient: str  # utterance id
    clinician: str  # utterance id of the response
    reason: str
    score: int


def build_candidates(utterances: list[Utterance], codings: list[Coding]) -> list[Candidate]:
    """Pair each significant verified patient utterance with the next verified clinician response."""
    by_id = {c.utterance: c for c in codings}
    order = {u.id: k for k, u in enumerate(utterances)}
    candidates: list[Candidate] = []
    for u in utterances:
        if u.role != "patient":
            continue
        pc = by_id.get(u.id)
        if pc is None or not pc.verified or pc.code not in SIGNIFICANT_PATIENT_CODES:
            continue
        response = _next_clinician_response(u, utterances, by_id)
        if response is None:
            continue
        rc = by_id[response.id]
        score = 2 if (pc.code == "CHANGE" or pc.emotions) else 1
        parts = []
        if pc.code == "CHANGE":
            parts.append("lenguaje de cambio")
        if pc.code == "SUSTAIN":
            parts.append("mantenimiento")
        if pc.emotions:
            parts.append("emoción: " + ", ".join(pc.emotions))
        if rc.code in WEAK_RESPONSE_CODES:
            score -= 1
            parts.append(f"respuesta débil ({rc.code})")
        if rc.code in STRONG_RESPONSE_CODES:
            score += 1
            parts.append(f"posible acierto ({rc.code})")
        candidates.append(
            Candidate(
                id=f"C{len(candidates) + 1:02d}",
                patient=u.id,
                clinician=response.id,
                reason="; ".join(parts),
                score=score,
            )
        )
    candidates.sort(key=lambda c: (-c.score, order[c.patient]))
    return candidates[:MAX_CANDIDATES]


def _next_clinician_response(
    patient_utt: Utterance, utterances: list[Utterance], by_id: dict[str, Coding]
) -> Utterance | None:
    """First verified clinician utterance after the patient's, in a later turn."""
    for u in utterances:
        if u.turn <= patient_utt.turn or u.role != "clinician":
            continue
        coding = by_id.get(u.id)
        if coding is not None and coding.verified and coding.code:
            return u
    return None


def save(candidates: list[Candidate], path: Path) -> None:
    path.write_text(
        json.dumps([asdict(c) for c in candidates], ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load(path: Path) -> list[Candidate]:
    return [Candidate(**c) for c in json.loads(path.read_text(encoding="utf-8"))]
