"""Command-line entry point.

    oarsight check                      # verify API keys and connectivity
    oarsight transcribe <audio>         # transcribe with speaker labels and check coverage
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import coverage
from .api import ApiError, ChatClient, TranscribeClient, baseten_client
from .config import SPARK_OPEN_BASETEN, MissingKeyError, load_settings
from .transcription import transcribe_file
from .usage import UsageLog


def _check() -> int:
    settings = load_settings()
    ok = True
    try:
        models = ChatClient(settings.require_meta_key()).list_models()
        print(f"Meta Model API: OK ({len(models)} models: {', '.join(sorted(models))})")
    except (MissingKeyError, ApiError) as exc:
        ok = False
        print(f"Meta Model API: FAILED - {exc}")
    if settings.baseten_api_key:
        try:
            client = baseten_client(settings.baseten_api_key)
            data = client.chat(
                "check", SPARK_OPEN_BASETEN, [{"role": "user", "content": "Reply with the word: ready"}],
                json_output=False,
            )
            answer = (data["choices"][0]["message"].get("content") or "").strip()
            print(f"Baseten ({SPARK_OPEN_BASETEN}): OK - {answer[:60]!r}")
        except ApiError as exc:
            ok = False
            print(f"Baseten: FAILED - {exc}")
    else:
        print("Baseten: skipped (BASETEN_API_KEY not set)")
    return 0 if ok else 1


def _transcribe(audio_path: Path, out_dir: Path | None, keywords: list[str] | None) -> int:
    settings = load_settings()
    session_dir = out_dir or settings.data_dir / "sessions" / audio_path.stem.replace(" ", "_")
    usage = UsageLog(settings.data_dir / "usage.jsonl")
    client = TranscribeClient(settings.require_meta_key(), usage=usage)
    transcript = transcribe_file(audio_path, client, session_dir, keywords=keywords)
    (session_dir / "transcript.json").write_text(transcript.to_json(), encoding="utf-8")
    cov = coverage.assess(transcript)

    for turn in transcript.turns:
        minutes, seconds = divmod(int(turn.start), 60)
        print(f"[{minutes}:{seconds:02d}] {turn.speaker or '?'}: {turn.text}")
    print()
    print(f"Turns: {len(transcript.turns)} | chunks: {len(transcript.chunks)} | duration: {transcript.duration:.0f} s")
    print(
        f"Coverage: {cov.fraction:.0%} of detected speech ({cov.covered_speech_seconds:.0f}/{cov.speech_seconds:.0f} s), "
        f"{cov.words} words, {cov.words_per_speech_minute:.0f} words/min"
    )
    for gap in cov.gaps:
        print(f"  Gap without transcript: {gap.start:.0f}-{gap.end:.0f} s")
    print(f"Cost: ${usage.total_cost:.4f} | saved to {session_dir / 'transcript.json'}")
    if not cov.complete:
        print("INCOMPLETE TRANSCRIPT: this session will not be analyzed.", file=sys.stderr)
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="oarsight", description="AI supervision for motivational interviewing")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="verify API keys and connectivity")
    tr = sub.add_parser("transcribe", help="transcribe an audio file with speaker labels")
    tr.add_argument("audio", type=Path)
    tr.add_argument("--out", type=Path, default=None, help="session folder (default: datos/sessions/<name>)")
    tr.add_argument("--keyword", action="append", dest="keywords", help="vocabulary bias term (repeatable)")
    args = parser.parse_args(argv)

    try:
        if args.command == "check":
            return _check()
        if args.command == "transcribe":
            return _transcribe(args.audio, args.out, args.keywords)
    except MissingKeyError as exc:
        print(exc, file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
