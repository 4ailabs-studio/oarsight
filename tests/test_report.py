from oarsight import report
from oarsight.coding import Coding
from oarsight.metrics import Metrics
from oarsight.moments import Candidate
from oarsight.supervisor import Moment
from oarsight.utterances import Utterance


def _metrics(**over):
    base = {
        "mode": "session",
        "clinician_counts": {},
        "clinician_coded": 20,
        "clinician_unverified": 0,
        "questions": 5,
        "reflections": 6,
        "reflections_per_question": 1.2,
        "pct_complex_reflections": 0.5,
        "mi_adherent": 2,
        "mi_non_adherent": 0,
        "pct_mi_adherent": 1.0,
        "patient_counts": {},
        "patient_coded": 10,
        "patient_unverified": 0,
        "change_talk_ratio": 0.4,
    }
    base.update(over)
    return Metrics(**base)


def test_choose_skill_follows_safety_first_then_furthest_metric():
    assert report.choose_skill(_metrics(mi_non_adherent=2)) == "ASK_PERMISSION"
    assert report.choose_skill(_metrics(reflections_per_question=0.3)) == "REFLECT_BEFORE_ASKING"
    assert report.choose_skill(_metrics(pct_complex_reflections=0.1)) == "COMPLEX_REFLECTIONS"
    assert report.choose_skill(_metrics(mi_adherent=0)) == "AFFIRM_COLLABORATE"
    assert report.choose_skill(_metrics()) == "CONSOLIDATE"


def test_choose_skill_ignores_complex_ratio_without_reflections():
    m = _metrics(reflections=1, pct_complex_reflections=0.0)
    assert report.choose_skill(m) == "CONSOLIDATE"


def _u(id, role, text):
    return Utterance(id=id, turn=0, speaker="c0:A", role=role, start=0.0, end=1.0, text=text)


def test_verify_strengths_keeps_only_literal_clinician_quotes():
    utts = [
        _u("U001", "clinician", "¿Qué le parece si lo revisamos juntos?"),
        _u("U002", "patient", "Quiero estar bien."),
    ]
    strengths, dropped = report.verify_strengths(
        {
            "strengths": [
                {"text": "Invitaste a decidir.", "quote": "lo revisamos juntos", "utterance": "U001"},
                {"text": "Inventada.", "quote": "frase que nadie dijo", "utterance": "U001"},
                {"text": "Del paciente.", "quote": "Quiero estar bien", "utterance": "U002"},
            ]
        },
        utts,
        [],
        [],
    )
    assert [s.utterance for s in strengths] == ["U001"]
    assert dropped == 2


def test_verify_strengths_falls_back_to_acierto_moments():
    utts = [_u("U004", "clinician", "Le da miedo picarse.")]
    moments = [
        Moment(
            candidate="C02",
            type="acierto",
            why="Reflejaste su miedo.",
            alternative="x",
            alternative_code="SIMPLE_REFLECTION",
            alternative_verified=True,
            attempts=1,
        )
    ]
    candidates = [Candidate(id="C02", patient="U003", clinician="U004", reason="x", score=2)]
    strengths, _ = report.verify_strengths({"strengths": []}, utts, moments, candidates)
    assert [(s.utterance, s.text) for s in strengths] == [("U004", "Reflejaste su miedo.")]


class _FakeModel:
    def __init__(self, answer):
        self.answer = answer

    def json(self, stage, system, user):
        assert stage == "report"
        return self.answer


def test_build_report_assembles_verified_report_with_brief_tools():
    utts = [_u("U001", "clinician", "¿Qué le parece si lo revisamos juntos?")]
    codings = [Coding("U001", "clinician", "SEEK_COLLABORATION", verified=True)]
    model = _FakeModel(
        {
            "pattern": "Respetas el ritmo.",
            "strengths": [{"text": "Colaboras.", "quote": "lo revisamos juntos", "utterance": "U001"}],
            "conclusions": ["Primera conclusión.", " ".join(["palabra"] * 40)],
        }
    )
    result = report.build_report(utts, codings, _metrics(mode="brief", mi_non_adherent=1), [], [], model)
    assert result.skill_id == "ASK_PERMISSION"  # chosen by code, not by the model
    assert len(result.strengths) == 1 and result.dropped_strengths == 0
    assert len(result.conclusions) == 2 and len(result.conclusions[1].split()) == 25
    assert [t["title"] for t in result.brief_tools] == [
        "Fijar la agenda juntos",
        "Preguntar-informar-preguntar",
        "Regla de importancia y confianza (0-10)",
    ]


def test_build_report_session_mode_has_no_brief_tools():
    model = _FakeModel({"pattern": "p", "strengths": [], "conclusions": []})
    result = report.build_report([], [], _metrics(), [], [], model)
    assert result.brief_tools == [] and result.conclusions == []
