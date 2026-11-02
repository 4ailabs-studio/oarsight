"""Command-line entry point.

oarsight check                      # verify API keys and connectivity
oarsight transcribe <audio>         # transcribe with speaker labels and check coverage
oarsight prepare <session-dir>      # assign speaker roles and split into utterances
oarsight code <session-dir>         # code utterances and compute metrics
oarsight codebook                   # print the coding scheme as Markdown
oarsight supervise <session-dir>    # choose key moments with verified alternatives
oarsight report <session-dir>       # expert report: pattern, strengths, skill, conclusions
oarsight serve                      # run the web interface
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import coding, coverage, metrics, moments, report, supervisor, utterances
from .api import ApiError, ChatClient, TranscribeClient, baseten_client, fireworks_client
from .codebook import render_markdown
from .config import SPARK_OPEN_BASETEN, SPARK_OPEN_FIREWORKS, MissingKeyError, load_settings
from .llm import BACKENDS, make_model
from .roles import assign_roles
from .transcription import Transcript, transcribe_file
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
                "check",
                SPARK_OPEN_BASETEN,
                [{"role": "user", "content": "Reply with the word: ready"}],
                json_output=False,
            )
            answer = (data["choices"][0]["message"].get("content") or "").strip()
            print(f"Baseten ({SPARK_OPEN_BASETEN}): OK - {answer[:60]!r}")
        except ApiError as exc:
            ok = False
            print(f"Baseten: FAILED - {exc}")
    else:
        print("Baseten: skipped (BASETEN_API_KEY not set)")
    if settings.fireworks_api_key:
        try:
            client = fireworks_client(settings.fireworks_api_key)
            data = client.chat(
                "check",
                SPARK_OPEN_FIREWORKS,
                [{"role": "user", "content": "Reply with the word: ready"}],
                json_output=False,
            )
            answer = (data["choices"][0]["message"].get("content") or "").strip()
            print(f"Fireworks ({SPARK_OPEN_FIREWORKS}): OK - {answer[:60]!r}")
        except ApiError as exc:
            ok = False
            print(f"Fireworks: FAILED - {exc}")
    else:
        print("Fireworks: skipped (FIREWORKS_API_KEY not set)")
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
    print(
        f"Turns: {len(transcript.turns)} | chunks: {len(transcript.chunks)} | duration: {transcript.duration:.0f} s"
    )
    print(
        f"Coverage: {cov.fraction:.0%} of detected speech ({cov.covered_speech_seconds:.0f}/{cov.speech_seconds:.0f} s), "
        f"{cov.words} words, {cov.words_per_speech_minute:.0f} words/min"
    )
    for gap in cov.gaps:
        print(f"  Gap without transcript: {gap.start:.0f}-{gap.end:.0f} s")
    print(f"Cost: {usage.cost_summary()} | saved to {session_dir / 'transcript.json'}")
    if not cov.complete:
        print("INCOMPLETE TRANSCRIPT: this session will not be analyzed.", file=sys.stderr)
        return 2
    return 0


def _prepare(session_dir: Path, backend: str) -> int:
    settings = load_settings()
    transcript = Transcript.from_json((session_dir / "transcript.json").read_text(encoding="utf-8"))
    usage = UsageLog(settings.data_dir / "usage.jsonl")
    roles = assign_roles(transcript, make_model(backend, settings, usage))
    utts = utterances.build_utterances(transcript, roles)
    utterances.save(utts, session_dir / "utterances.json")

    print(f"Roles ({backend}):")
    for label, sr in roles.speakers.items():
        mark = "verified" if sr.verified else "NOT verified"
        print(f"  {label} -> {sr.role} ({sr.confidence}, evidence {mark})")
    if roles.notes:
        print(f"  Notes: {roles.notes}")
    counts: dict[str, int] = {}
    for u in utts:
        counts[u.role] = counts.get(u.role, 0) + 1
    print(f"Utterances: {len(utts)} " + " ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    long_ones = [u.id for u in utts if u.is_long]
    if long_ones:
        print(f"Long utterances to review: {', '.join(long_ones)}")
    print(f"Cost: {usage.cost_summary()} | saved to {session_dir / 'utterances.json'}")
    if roles.needs_confirmation:
        print("NEEDS CONFIRMATION:", *roles.needs_confirmation, sep="\n  ", file=sys.stderr)
        return 2
    return 0


def _fmt_ratio(value: float | None) -> str:
    return f"{value:.2f}" if value is not None else "n/a"


def _code(session_dir: Path, backend: str, effort: str | None, redact_pii: bool) -> int:
    settings = load_settings()
    utts = utterances.load(session_dir / "utterances.json")
    usage = UsageLog(settings.data_dir / "usage.jsonl")
    codings, _shown, redacted = coding.code_session(
        utts, make_model(backend, settings, usage, reasoning_effort=effort), redact_pii=redact_pii
    )
    coding.save(codings, session_dir / "coding.json")
    report = metrics.compute(utts, codings)
    metrics.save(report, session_dir / "metrics.json")

    verified = sum(1 for c in codings if c.verified)
    print(f"Coding ({backend}): {verified}/{len(codings)} verified, {redacted} identifier(s) redacted")
    for c in codings:
        if c.verified:
            print(f"  {c.utterance} [{c.family}] {c.code} ({c.confidence})")
        else:
            print(f"  {c.utterance} [{c.family}] REJECTED: {c.rejection}")
    print(f"Mode: {report.mode} ({report.clinician_coded} coded clinician utterances)")
    print(
        f"Reflections/question: {_fmt_ratio(report.reflections_per_question)} | "
        f"% complex: {_fmt_ratio(report.pct_complex_reflections)} | "
        f"% MI-adherent: {_fmt_ratio(report.pct_mi_adherent)}"
    )
    print(f"Change-talk ratio: {_fmt_ratio(report.change_talk_ratio)}")
    print(f"Cost: {usage.cost_summary()} | saved to {session_dir / 'coding.json'}")
    return 0


def _supervise(session_dir: Path, backend: str, effort: str | None) -> int:
    settings = load_settings()
    utts = utterances.load(session_dir / "utterances.json")
    codings = coding.load(session_dir / "coding.json")
    usage = UsageLog(settings.data_dir / "usage.jsonl")
    candidates = moments.build_candidates(utts, codings)
    moments.save(candidates, session_dir / "candidates.json")
    results = supervisor.supervise(
        candidates, utts, codings, make_model(backend, settings, usage, reasoning_effort=effort)
    )
    supervisor.save(results, session_dir / "moments.json")

    print(f"Candidates ({backend}): {len(candidates)}")
    for c in candidates:
        print(f"  {c.id} score={c.score}: {c.reason}")
    print(f"Moments: {len(results)}")
    for m in results:
        mark = "verified" if m.alternative_verified else f"NOT verified ({m.note})"
        print(f"  {m.candidate} [{m.type}] {m.why}")
        print(f"    Podrías decir ({m.alternative_code}, {mark}): {m.alternative}")
    print(f"Cost: {usage.cost_summary()} | saved to {session_dir / 'moments.json'}")
    return 0


def _report(session_dir: Path, backend: str, effort: str | None) -> int:
    settings = load_settings()
    missing = [
        n
        for n in ("utterances", "coding", "metrics", "candidates", "moments")
        if not (session_dir / f"{n}.json").exists()
    ]
    if missing:
        print(f"Missing files: {', '.join(missing)}. Run prepare, code and supervise first.", file=sys.stderr)
        return 2
    utts = utterances.load(session_dir / "utterances.json")
    codings = coding.load(session_dir / "coding.json")
    report_metrics = metrics.load(session_dir / "metrics.json")
    candidates = moments.load(session_dir / "candidates.json")
    session_moments = supervisor.load(session_dir / "moments.json")
    usage = UsageLog(settings.data_dir / "usage.jsonl")
    result = report.build_report(
        utts,
        codings,
        report_metrics,
        candidates,
        session_moments,
        make_model(backend, settings, usage, reasoning_effort=effort),
    )
    report.save(result, session_dir / "report.json")

    skill = report.SKILLS[result.skill_id]
    print(f"Pattern ({backend}): {result.pattern}")
    print(f"Skill to practice: {skill['title']}")
    print(f"Strengths: {len(result.strengths)} verified ({result.dropped_strengths} dropped)")
    for s in result.strengths:
        print(f"  - {s.text} [{s.utterance}: {s.quote[:60]}…]")
    print("Conclusions:")
    for c in result.conclusions:
        print(f"  - {c}")
    if result.brief_tools:
        print(f"Brief tools: {len(result.brief_tools)} included")
    print(f"Cost: {usage.cost_summary()} | saved to {session_dir / 'report.json'}")
    return 0


def _serve(host: str, port: int) -> int:
    import uvicorn

    from .web import app

    print(f"Oarsight at http://{host}:{port} (Ctrl+C to stop)")
    uvicorn.run(app, host=host, port=port, log_level="warning")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="oarsight", description="AI supervision for motivational interviewing"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="verify API keys and connectivity")
    tr = sub.add_parser("transcribe", help="transcribe an audio file with speaker labels")
    tr.add_argument("audio", type=Path)
    tr.add_argument("--out", type=Path, default=None, help="session folder (default: datos/sessions/<name>)")
    tr.add_argument("--keyword", action="append", dest="keywords", help="vocabulary bias term (repeatable)")
    pr = sub.add_parser("prepare", help="assign speaker roles and split into utterances")
    pr.add_argument("session", type=Path, help="session folder containing transcript.json")
    pr.add_argument(
        "--model", choices=BACKENDS, default="wonder", help="spark-open = private mode on Baseten"
    )
    co = sub.add_parser("code", help="code utterances with the MITI codebook and compute metrics")
    co.add_argument("session", type=Path, help="session folder containing utterances.json")
    co.add_argument("--model", choices=BACKENDS, default="spark", help="spark-open = private mode on Baseten")
    co.add_argument("--effort", default="low", help="reasoning effort (default: low; ignored by spark-open)")
    co.add_argument("--no-redact", action="store_true", help="skip PII redaction (not recommended)")
    cb = sub.add_parser("codebook", help="print the coding scheme as Markdown")
    cb.add_argument("--write", type=Path, default=None, help="write to a file instead of printing")
    su = sub.add_parser("supervise", help="choose key moments with verified alternatives")
    su.add_argument("session", type=Path, help="session folder containing utterances.json and coding.json")
    su.add_argument("--model", choices=BACKENDS, default="wonder")
    su.add_argument("--effort", default=None, help="reasoning effort (default: model default)")
    rp = sub.add_parser("report", help="expert report: pattern, strengths, skill, conclusions")
    rp.add_argument("session", type=Path, help="session folder with utterances/coding/metrics/moments")
    rp.add_argument("--model", choices=BACKENDS, default="wonder")
    rp.add_argument("--effort", default=None, help="reasoning effort (default: model default)")
    sv = sub.add_parser("serve", help="run the web interface")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)

    try:
        if args.command == "check":
            return _check()
        if args.command == "transcribe":
            return _transcribe(args.audio, args.out, args.keywords)
        if args.command == "prepare":
            return _prepare(args.session, args.model)
        if args.command == "code":
            return _code(args.session, args.model, args.effort, not args.no_redact)
        if args.command == "supervise":
            return _supervise(args.session, args.model, args.effort)
        if args.command == "report":
            return _report(args.session, args.model, args.effort)
        if args.command == "serve":
            return _serve(args.host, args.port)
        if args.command == "codebook":
            text = render_markdown()
            if args.write:
                args.write.parent.mkdir(parents=True, exist_ok=True)
                args.write.write_text(text + "\n", encoding="utf-8")
            else:
                print(text)
            return 0
    except MissingKeyError as exc:
        print(exc, file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
