from oarsight import moments, supervisor
from oarsight.coding import Coding
from oarsight.moments import Candidate
from oarsight.utterances import Utterance


def _u(id, role, text, turn):
    return Utterance(id=id, turn=turn, speaker="c0:A", role=role, start=0.0, end=1.0, text=text)


def _session():
    utts = [
        _u("U001", "patient", "Quiero estar bien para mi nieta.", 0),
        _u("U002", "clinician", "¿Desde cuándo se siente así?", 1),
        _u("U003", "patient", "Insulina no, doctor.", 2),
        _u("U004", "clinician", "Le da miedo picarse.", 3),
        _u("U005", "patient", "Trabajo en un taller.", 4),
        _u("U006", "clinician", "Ok.", 5),
    ]
    codings = [
        Coding("U001", "patient", "CHANGE", verified=True),
        Coding("U002", "clinician", "QUESTION", verified=True),
        Coding("U003", "patient", "SUSTAIN", verified=True),
        Coding("U004", "clinician", "SIMPLE_REFLECTION", verified=True),
        Coding("U005", "patient", "NEUTRAL", verified=True),
        Coding("U006", "clinician", None, verified=False, rejection="x"),
    ]
    return utts, codings


def test_build_candidates_pairs_significant_moments_and_scores():
    candidates = moments.build_candidates(*_session())
    # sorted by score: sustain + reflection first, change + question second
    assert [(c.patient, c.clinician) for c in candidates] == [("U003", "U004"), ("U001", "U002")]
    first, second = candidates
    assert first.score == 2  # sustain (1) with a reflection (+1)
    assert "posible acierto" in first.reason
    assert second.score == 1  # change (2) with a weak question response (-1)
    assert "lenguaje de cambio" in second.reason and "débil" in second.reason


def test_build_candidates_skips_neutral_and_unverified():
    utts, codings = _session()
    codings[0] = Coding("U001", "patient", None, verified=False, rejection="x")
    candidates = moments.build_candidates(utts, codings)
    assert [c.patient for c in candidates] == ["U003"]  # U001 unverified, U005 neutral


class _FakeModel:
    def __init__(self, script):
        self.script = {stage: list(answers) for stage, answers in script.items()}
        self.calls = []

    def json(self, stage, system, user):
        self.calls.append(stage)
        return self.script[stage].pop(0)


def _candidate():
    return Candidate(id="C01", patient="U001", clinician="U002", reason="cambio", score=1)


def test_supervise_verifies_first_try_alternative():
    utts, codings = _session()
    model = _FakeModel(
        {
            "supervise": [
                {
                    "moments": [
                        {
                            "candidate": "C01",
                            "type": "oportunidad",
                            "why": "El paciente se abrió y respondiste preguntando.",
                            "alternative": "Su nieta le importa mucho.",
                            "code": "COMPLEX_REFLECTION",
                        }
                    ]
                }
            ],
            "verify-alternative": [
                {"codes": [{"id": "ALT", "code": "COMPLEX_REFLECTION", "quote": "Su nieta le importa"}]}
            ],
        }
    )
    (moment,) = supervisor.supervise([_candidate()], utts, codings, model)
    assert moment.alternative_verified and moment.attempts == 1
    assert moment.alternative_code == "COMPLEX_REFLECTION"
    assert model.calls == ["supervise", "verify-alternative"]


def test_supervise_regenerates_after_mismatch_then_gives_up():
    utts, codings = _session()
    model = _FakeModel(
        {
            "supervise": [
                {
                    "moments": [
                        {
                            "candidate": "C01",
                            "type": "oportunidad",
                            "why": "Importa.",
                            "alternative": "Su nieta le importa mucho.",
                            "code": "COMPLEX_REFLECTION",
                        }
                    ]
                }
            ],
            "verify-alternative": [
                {"codes": [{"id": "ALT", "code": "SIMPLE_REFLECTION", "quote": "Su nieta le importa"}]},
                {"codes": [{"id": "ALT", "code": "SIMPLE_REFLECTION", "quote": "quiere estar bien"}]},
                {"codes": [{"id": "ALT", "code": "QUESTION", "quote": "qué le importa"}]},
            ],
            "propose-alternative": [
                {"alternative": "Quiere estar bien para su nieta.", "code": "COMPLEX_REFLECTION"},
                {"alternative": "¿Qué le importa de su nieta?", "code": "COMPLEX_REFLECTION"},
            ],
        }
    )
    (moment,) = supervisor.supervise([_candidate()], utts, codings, model)
    assert not moment.alternative_verified
    assert moment.attempts == 3
    assert "instead of" in moment.note


def test_supervise_rejects_bad_entries_truncates_and_caps():
    utts, codings = _session()
    cands = [
        _candidate(),
        Candidate(id="C02", patient="U003", clinician="U004", reason="x", score=2),
        Candidate(id="C03", patient="U003", clinician="U004", reason="x", score=0),
        Candidate(id="C04", patient="U003", clinician="U004", reason="x", score=0),
    ]
    long_why = " ".join(f"palabra{i}" for i in range(60))
    model = _FakeModel(
        {
            "supervise": [
                {
                    "moments": [
                        {
                            "candidate": "C99",
                            "type": "oportunidad",
                            "why": "x",
                            "alternative": "Y.",
                            "code": "AFFIRM",
                        },
                        {
                            "candidate": "C01",
                            "type": "triunfo",
                            "why": "x",
                            "alternative": "Y.",
                            "code": "AFFIRM",
                        },
                        {
                            "candidate": "C01",
                            "type": "acierto",
                            "why": long_why,
                            "alternative": "Qué bueno que vino hoy.",
                            "code": "AFFIRM",
                        },
                        {
                            "candidate": "C02",
                            "type": "oportunidad",
                            "why": "y",
                            "alternative": "Le da miedo picarse.",
                            "code": "SIMPLE_REFLECTION",
                        },
                        {
                            "candidate": "C01",
                            "type": "oportunidad",
                            "why": "duplicado",
                            "alternative": "Z.",
                            "code": "AFFIRM",
                        },
                        {
                            "candidate": "C03",
                            "type": "oportunidad",
                            "why": "y",
                            "alternative": "W.",
                            "code": "AFFIRM",
                        },
                        {
                            "candidate": "C04",
                            "type": "oportunidad",
                            "why": "de más",
                            "alternative": "V.",
                            "code": "AFFIRM",
                        },
                    ]
                }
            ],
            "verify-alternative": [
                {"codes": [{"id": "ALT", "code": "AFFIRM", "quote": "Qué bueno que vino"}]},
                {"codes": [{"id": "ALT", "code": "SIMPLE_REFLECTION", "quote": "Le da miedo picarse"}]},
                {"codes": [{"id": "ALT", "code": "AFFIRM", "quote": "W"}]},
            ],
        }
    )
    result = supervisor.supervise(cands, utts, codings, model)
    assert [m.candidate for m in result] == ["C01", "C02", "C03"]  # unknown, bad type, dupe, 4th dropped
    assert len(result[0].why.split()) == 40
    assert all(m.alternative_verified for m in result)


def test_check_alternative_rejects_long_text_and_bad_codes_without_calling():
    utts, _ = _session()
    model = _FakeModel({})
    ok, actual = supervisor.check_alternative(" ".join(["palabra"] * 21), "AFFIRM", utts[0], model)
    assert (ok, actual) == (False, None)
    ok, actual = supervisor.check_alternative("Corta.", "NO_ES_CODIGO", utts[0], model)
    assert (ok, actual) == (False, None)
    assert model.calls == []


def test_supervise_without_candidates_returns_empty():
    utts, codings = _session()
    assert supervisor.supervise([], utts, codings, _FakeModel({})) == []
