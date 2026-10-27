# Build log

What was built during the Meta Global AI Developer Hackathon, day by day. Times are US Eastern (ET). The commit history is the detailed record.

## Before the kickoff (Oct 25 – Oct 26, 12:00 ET)

Not part of the submission:

- Research on the problem, the MITI coding scheme, related work and existing tools.
- Small throwaway experiments with the Meta Model API to check feasibility (transcription, speaker separation, coding prompts). That code is not in this repository.

Repository scaffolding, created on Oct 26 at 11:04–11:18 ET, before the 12:00 ET kickoff: `README.md`, `.gitignore`, `.env.example`. No product code.

## Day 0 — Mon, Oct 26 (kickoff)

- Repository made public with secret scanning and push protection enabled.
- README aligned with the hackathon rules: submission details, prior-work disclosure, scope ("what Oarsight is not"), data and privacy, third-party data.
- MIT license.
- This build log.

## Day 1 — Tue, Oct 27

Foundations, written from scratch:

- Python project (`uv`, Python 3.13) with an `oarsight` command-line tool.
- `api.py`: clients for Meta Model API (chat, model list) and Muse Voice Transcribe's file endpoint, plus an OpenAI-compatible client for Muse Spark Open on Baseten. Retries with backoff and jitter on 429/5xx.
- `usage.py`: every model call is logged with stage, tokens, reasoning tokens, cached tokens, latency and estimated cost.
- `audio.py`: conversion to mono 24 kHz WAV, chunking under the 10-minute limit with overlap, and speech detection with ffmpeg.
- `transcription.py`: transcription with speaker labels and turn timestamps from Muse Voice Transcribe; chunks merged without duplicating overlapping turns; speaker labels kept per chunk. The transcript text always comes from the speech model and is never rewritten.
- `coverage.py`: the coverage check. Compares transcribed turns with the speech actually detected in the audio, reports gaps longer than 20 s, and refuses to analyze a session below 80 % coverage.
- 16 automated tests (no network): chunking, speech detection, chunk merging, coverage, costs, JSON parsing, retries.
- First real run on a fictional role-played consultation (4 min 40 s): 28 turns, both speakers separated, 100 % of detected speech covered, cost about $0.014.
