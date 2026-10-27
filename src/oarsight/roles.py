"""Speaker roles: who is the clinician, who is the patient.

Voice Transcribe labels speakers A, B, ... within each chunk. A language model maps each label to a role and must
justify it with literal quotes from that speaker. The code checks every quote and that the session has exactly the
roles needed for analysis; anything doubtful is returned as "needs confirmation" for the clinician to resolve.
The model never sees an instruction to edit the transcript, and its output cannot change it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .llm import Model
from .text import is_literal_quote
from .transcription import Transcript

ROLES = ("clinician", "patient", "companion", "unknown")

SYSTEM_PROMPT = """You prepare transcripts of clinical consultations (Spanish, often from Mexico) for a tool that gives \
clinicians feedback on their motivational interviewing.

The transcript comes from a speech-recognition model that labels speakers per chunk (for example "c0:A", "c0:B"). \
Decide the role of each speaker label:
- "clinician": the doctor or health professional (asks about symptoms, explains treatment, gives instructions).
- "patient": the person whose health is discussed (talks about their own symptoms, habits, fears, medications).
- "companion": a relative or companion of the patient.
- "unknown": not enough information.

Rules:
- Justify each label with 1 or 2 short LITERAL quotes copied exactly from that speaker's turns.
- Confidence is "high", "medium" or "low".
- If a label seems to contain two different people, say so in "notes".

Answer with JSON only:
{"speakers": {"<label>": {"role": "...", "confidence": "...", "evidence": ["literal quote"]}}, "notes": "..."}"""


@dataclass
class SpeakerRole:
    role: str
    confidence: str
    evidence: list[str] = field(default_factory=list)
    verified: bool = False  # True when every evidence quote was found in that speaker's turns


@dataclass
class RoleAssignment:
    speakers: dict[str, SpeakerRole]
    notes: str = ""
    needs_confirmation: list[str] = field(default_factory=list)

    def role_of(self, label: str | None) -> str:
        if label is None or label not in self.speakers:
            return "unknown"
        return self.speakers[label].role


def format_turns(transcript: Transcript) -> str:
    lines = []
    for turn in transcript.turns:
        minutes, seconds = divmod(int(turn.start), 60)
        lines.append(f"[{minutes}:{seconds:02d}] {turn.speaker or 'unlabeled'}: {turn.text}")
    return "\n".join(lines)


def validate(raw: dict, transcript: Transcript) -> RoleAssignment:
    """Check the model's answer against the transcript and list what a human must confirm."""
    labels = sorted({t.speaker for t in transcript.turns if t.speaker})
    text_by_label = {label: " ".join(t.text for t in transcript.turns if t.speaker == label) for label in labels}
    speakers: dict[str, SpeakerRole] = {}
    needs: list[str] = []

    for label in labels:
        entry = (raw.get("speakers") or {}).get(label) or {}
        role = entry.get("role") if entry.get("role") in ROLES else "unknown"
        evidence = [q for q in entry.get("evidence") or [] if isinstance(q, str)]
        verified = bool(evidence) and all(is_literal_quote(q, text_by_label[label]) for q in evidence)
        confidence = entry.get("confidence") if entry.get("confidence") in ("high", "medium", "low") else "low"
        speakers[label] = SpeakerRole(role, confidence, evidence, verified)
        if role == "unknown" or confidence == "low" or not verified:
            needs.append(f"{label}: role '{role}' needs confirmation")

    assigned = [s.role for s in speakers.values()]
    if "clinician" not in assigned:
        needs.append("no speaker was identified as the clinician")
    if "patient" not in assigned:
        needs.append("no speaker was identified as the patient")
    if any(t.speaker is None for t in transcript.turns):
        needs.append("some turns have no speaker label")
    return RoleAssignment(speakers=speakers, notes=str(raw.get("notes") or ""), needs_confirmation=needs)


def assign_roles(transcript: Transcript, model: Model) -> RoleAssignment:
    raw = model.json("roles", SYSTEM_PROMPT, format_turns(transcript))
    return validate(raw if isinstance(raw, dict) else {}, transcript)
