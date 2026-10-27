import pytest

from oarsight import codebook
from oarsight.config import Settings
from oarsight.llm import make_model
from oarsight.roles import RoleAssignment, SpeakerRole, validate
from oarsight.text import is_literal_quote, normalize
from oarsight.transcription import Transcript, Turn
from oarsight.utterances import build_utterances, split_text


def _transcript():
    return Transcript(
        source="t",
        duration=60.0,
        turns=[
            Turn(0, 10, "Sí, doctor. Me asusta eso de la insulina, mi compadre quedó ciego.", "c0:A", 0),
            Turn(10, 12, "Ok. ¿De qué quedó mal?", "c0:B", 0),
            Turn(12, 20, "De los ojos, dicen que ya no ve igual.", "c0:A", 0),
        ],
    )


def test_normalize_and_literal_quotes():
    assert normalize("¿Qué HACE que se le olvide?") == "que hace que se le olvide"
    assert is_literal_quote("me asusta eso de la insulina", "Sí, doctor. Me asusta eso de la INSULINA, mi...")
    assert not is_literal_quote("me da miedo la insulina", "Me asusta eso de la insulina")
    assert not is_literal_quote("", "anything")


def test_split_text_on_sentences_and_opening_question_marks():
    assert split_text("Ok. ¿De qué quedó mal?") == ["Ok.", "¿De qué quedó mal?"]
    assert split_text("ok has investigado ¿para qué sirve la insulina?") == [
        "ok has investigado", "¿para qué sirve la insulina?"
    ]
    assert split_text("Bueno") == ["Bueno"]


def test_validate_accepts_verified_roles():
    raw = {"speakers": {
        "c0:A": {"role": "patient", "confidence": "high", "evidence": ["me asusta eso de la insulina"]},
        "c0:B": {"role": "clinician", "confidence": "high", "evidence": ["¿De qué quedó mal?"]},
    }}
    roles = validate(raw, _transcript())
    assert roles.role_of("c0:A") == "patient"
    assert roles.speakers["c0:B"].verified
    assert roles.needs_confirmation == []


def test_validate_flags_invented_evidence_and_missing_clinician():
    raw = {"speakers": {
        "c0:A": {"role": "patient", "confidence": "high", "evidence": ["frase que nunca se dijo"]},
        "c0:B": {"role": "patient", "confidence": "medium", "evidence": ["¿De qué quedó mal?"]},
    }}
    roles = validate(raw, _transcript())
    assert not roles.speakers["c0:A"].verified
    assert any("c0:A" in n for n in roles.needs_confirmation)
    assert any("clinician" in n for n in roles.needs_confirmation)


def test_validate_rejects_unknown_role_values():
    raw = {"speakers": {"c0:A": {"role": "doctor", "confidence": "high", "evidence": ["Sí, doctor"]}}}
    roles = validate(raw, _transcript())
    assert roles.role_of("c0:A") == "unknown"


def test_utterances_keep_exact_text_and_roles():
    roles = RoleAssignment(speakers={"c0:A": SpeakerRole("patient", "high"), "c0:B": SpeakerRole("clinician", "high")})
    utts = build_utterances(_transcript(), roles)
    assert [u.role for u in utts] == ["patient", "patient", "clinician", "clinician", "patient"]
    assert utts[3].text == "¿De qué quedó mal?"
    turns = _transcript().turns
    assert all(u.text in turns[u.turn].text for u in utts)
    assert [u.id for u in utts] == ["U001", "U002", "U003", "U004", "U005"]


def test_codebook_is_complete_and_renders():
    assert set(codebook.MI_ADHERENT | codebook.MI_NON_ADHERENT | codebook.REFLECTIONS) <= set(
        codebook.CLINICIAN_CODE_NAMES
    )
    assert "NO_CODE" in codebook.CLINICIAN_CODE_NAMES
    text = codebook.render(codebook.CLINICIAN_CODES)
    assert "Yo te voy a escuchar." in text  # leniency counter-example is present
    assert codebook.render(codebook.CLINICIAN_CODES) == text  # stable for prompt caching


def test_unknown_backend_is_rejected():
    with pytest.raises(ValueError):
        make_model("gpt", Settings(meta_api_key="k", baseten_api_key=None, data_dir=None))
