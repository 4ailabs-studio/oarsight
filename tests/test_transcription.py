from oarsight.audio import Interval
from oarsight.transcription import Transcript, Turn, merge_chunks, turns_from_response


def test_response_turns_are_placed_on_the_global_timeline_and_empty_ones_dropped():
    data = {
        "turns": [
            {"turnId": 1, "startMs": 1100, "endMs": 12900, "transcript": "Sí, doctor.", "speaker": "A"},
            {"turnId": 2, "startMs": 13000, "endMs": 13100, "transcript": "", "speaker": None},
            {"turnId": 3, "startMs": 13600, "endMs": 15700, "transcript": "¿De qué quedó mal?", "speaker": "B"},
        ]
    }
    turns = turns_from_response(data, chunk_index=1, offset=588.0)
    assert [t.text for t in turns] == ["Sí, doctor.", "¿De qué quedó mal?"]
    assert turns[0].start == 589.1
    assert turns[1].speaker == "c1:B"  # speaker labels are scoped to their chunk


def test_turns_in_the_overlap_are_kept_once():
    chunks = [Interval(0, 590), Interval(588, 900)]
    first = [Turn(10, 20, "a", "c0:A", 0), Turn(588.5, 591, "overlap seen by chunk 0", "c0:B", 0)]
    second = [Turn(588.6, 591, "overlap seen by chunk 1", "c1:A", 1), Turn(600, 610, "b", "c1:B", 1)]
    merged = merge_chunks([first, second], chunks, overlap=2.0)
    assert [t.text for t in merged] == ["a", "overlap seen by chunk 0", "b"]


def test_transcript_round_trips_through_json():
    original = Transcript(
        source="x.mp3",
        duration=10.0,
        turns=[Turn(0.5, 2.0, "Hola", "c0:A", 0)],
        speech=[Interval(0.4, 2.1)],
        chunks=[Interval(0.0, 10.0)],
    )
    assert Transcript.from_json(original.to_json()) == original
