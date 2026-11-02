"""Session metrics, computed in code from verified codes only (stage 7).

Only codings the verifier accepted count. Sessions with fewer than 20 coded
clinician utterances are "brief": ratios are still reported, but there are no
global scores, only moments.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .codebook import MI_ADHERENT, MI_NON_ADHERENT, REFLECTIONS
from .coding import Coding
from .utterances import Utterance

SESSION_MIN_CLINICIAN_UTTERANCES = 20


@dataclass
class Metrics:
    mode: str  # "session" or "brief"
    clinician_counts: dict[str, int]
    clinician_coded: int
    clinician_unverified: int
    questions: int
    reflections: int
    reflections_per_question: float | None
    pct_complex_reflections: float | None
    mi_adherent: int
    mi_non_adherent: int
    pct_mi_adherent: float | None
    patient_counts: dict[str, int]
    patient_coded: int
    patient_unverified: int
    change_talk_ratio: float | None  # CHANGE / (CHANGE + SUSTAIN)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, text: str) -> Metrics:
        return cls(**json.loads(text))


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def compute(utterances: list[Utterance], codings: list[Coding]) -> Metrics:
    by_id = {c.utterance: c for c in codings}
    clinician_counts: dict[str, int] = {}
    patient_counts: dict[str, int] = {}
    clinician_coded = clinician_unverified = patient_coded = patient_unverified = 0

    for u in utterances:
        coding = by_id.get(u.id)
        if u.role == "clinician":
            if coding is not None and coding.verified and coding.code:
                clinician_counts[coding.code] = clinician_counts.get(coding.code, 0) + 1
                clinician_coded += 1
            else:
                clinician_unverified += 1
        elif u.role == "patient":
            if coding is not None and coding.verified and coding.code:
                patient_counts[coding.code] = patient_counts.get(coding.code, 0) + 1
                patient_coded += 1
            else:
                patient_unverified += 1

    questions = clinician_counts.get("QUESTION", 0)
    complex_ = clinician_counts.get("COMPLEX_REFLECTION", 0)
    reflections = sum(clinician_counts.get(c, 0) for c in REFLECTIONS)
    adherent = sum(clinician_counts.get(c, 0) for c in MI_ADHERENT)
    non_adherent = sum(clinician_counts.get(c, 0) for c in MI_NON_ADHERENT)
    change = patient_counts.get("CHANGE", 0)
    sustain = patient_counts.get("SUSTAIN", 0)

    return Metrics(
        mode="session" if clinician_coded >= SESSION_MIN_CLINICIAN_UTTERANCES else "brief",
        clinician_counts=clinician_counts,
        clinician_coded=clinician_coded,
        clinician_unverified=clinician_unverified,
        questions=questions,
        reflections=reflections,
        reflections_per_question=_ratio(reflections, questions),
        pct_complex_reflections=_ratio(complex_, reflections),
        mi_adherent=adherent,
        mi_non_adherent=non_adherent,
        pct_mi_adherent=_ratio(adherent, adherent + non_adherent),
        patient_counts=patient_counts,
        patient_coded=patient_coded,
        patient_unverified=patient_unverified,
        change_talk_ratio=_ratio(change, change + sustain),
    )


def save(metrics: Metrics, path: Path) -> None:
    path.write_text(metrics.to_json(), encoding="utf-8")


def load(path: Path) -> Metrics:
    return Metrics.from_json(path.read_text(encoding="utf-8"))
