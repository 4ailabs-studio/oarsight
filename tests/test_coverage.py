from oarsight.audio import Interval
from oarsight.coverage import assess, subtract, union
from oarsight.transcription import Transcript, Turn


def _transcript(turns, speech, duration=600.0):
    return Transcript(source="t", duration=duration, turns=turns, speech=speech)


def test_union_and_subtract():
    assert union([Interval(5, 10), Interval(0, 6), Interval(20, 30)]) == [Interval(0, 10), Interval(20, 30)]
    assert subtract([Interval(0, 100)], [Interval(10, 20), Interval(50, 60)]) == [
        Interval(0, 10), Interval(20, 50), Interval(60, 100)
    ]


def test_full_transcript_is_complete():
    speech = [Interval(0, 100)]
    turns = [Turn(s, s + 9.5, "uno dos tres", "c0:A", 0) for s in range(0, 100, 10)]
    cov = assess(_transcript(turns, speech, duration=100))
    assert cov.complete
    assert cov.fraction == 1.0
    assert cov.gaps == []


def test_transcript_missing_most_speech_is_rejected():
    # Like the real failure we saw: ~10 minutes of conversation, only the first 2.5 transcribed.
    speech = [Interval(0, 600)]
    turns = [Turn(s, s + 9, "texto", "c0:A", 0) for s in range(0, 150, 10)]
    cov = assess(_transcript(turns, speech))
    assert not cov.complete
    assert cov.fraction < 0.3
    assert cov.gaps and cov.gaps[0].start >= 140


def test_short_pauses_are_not_reported_as_gaps():
    speech = [Interval(0, 100)]
    turns = [Turn(0, 40, "a", "c0:A", 0), Turn(52, 100, "b", "c0:B", 0)]  # 12 s untranscribed
    cov = assess(_transcript(turns, speech, duration=100))
    assert cov.gaps == []
    assert cov.complete
