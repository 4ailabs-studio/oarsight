from itertools import pairwise

from oarsight.audio import Interval, parse_silencedetect, plan_chunks


def test_short_audio_is_a_single_chunk():
    assert plan_chunks(279.6) == [Interval(0.0, 279.6)]


def test_long_audio_is_split_with_overlap_and_covers_everything():
    chunks = plan_chunks(1500.0, max_len=590.0, overlap=2.0)
    assert chunks[0] == Interval(0.0, 590.0)
    assert chunks[1].start == 588.0
    assert chunks[-1].end == 1500.0
    assert all(c.length <= 590.0 for c in chunks)
    assert all(nxt.start < cur.end for cur, nxt in pairwise(chunks))


def test_silencedetect_output_becomes_speech_intervals():
    stderr = (
        "[silencedetect @ 0x1] silence_start: 0\n"
        "[silencedetect @ 0x1] silence_end: 4.5 | silence_duration: 4.5\n"
        "[silencedetect @ 0x1] silence_start: 20\n"
        "[silencedetect @ 0x1] silence_end: 30 | silence_duration: 10\n"
        "[silencedetect @ 0x1] silence_start: 55\n"
    )
    assert parse_silencedetect(stderr, duration=60.0) == [Interval(4.5, 20.0), Interval(30.0, 55.0)]


def test_audio_without_silence_is_all_speech():
    assert parse_silencedetect("", duration=12.0) == [Interval(0.0, 12.0)]
