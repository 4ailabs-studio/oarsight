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

Later the same day:

- `llm.py`: interchangeable backends. Every analysis stage can run on Muse Wonder, Muse Spark, or **Muse Spark Open on Baseten (private mode)** with the same code.
- `roles.py`: maps each speaker label to clinician, patient or companion. The model must justify each role with literal quotes; the code verifies every quote and flags anything doubtful for human confirmation. The transcript is never modified.
- `utterances.py`: deterministic split of turns into utterances (sentence punctuation and opening `¿`/`¡`). Each utterance is an exact substring of its turn, so later quotes stay traceable.
- `codebook.py` and [`docs/CODEBOOK.md`](CODEBOOK.md): clinician behaviors and patient language, following MITI 4.2.1 categories, written in our own words with invented Mexican-Spanish examples and "not this" counter-examples aimed at the leniency we saw in early tests.
- `oarsight prepare` and `oarsight codebook` commands; usage log marks calls without a known price instead of counting them as free.
- 25 offline tests.
- Real run on the fictional consultation with **both Muse Wonder and Muse Spark Open**: identical roles (both verified by quote) and the same 36 utterances (17 clinician, 19 patient).
- [`docs/GUARDRAILS.md`](GUARDRAILS.md): catalog of every guardrail (scope, privacy, transcription fidelity, speakers, coding, feedback, agents, simulated patient, cost), each marked as implemented or planned with its day.
- New guardrail in code: Contributor-mode models are refused before any request is sent, so consultation content can never be used for training. 26 offline tests.

## Day 6 — Sun, Nov 1 → Mon, Nov 2 (catch-up)

Utterance coding and metrics, written from scratch:

- `redact.py`: minimal redaction of personal identifiers (phone, e-mail, CURP, NSS, dates) on the copy an analysis model sees; the transcript is never modified.
- `coding.py`: clinician coder (5a) and patient coder (5b, with emotions/needs 5c folded into the same call). Each coder gets the session in one batched call with the codebook first (cache-friendly prefix), targets marked and prior turns as context; the transcript travels inside delimiters as data, not instructions. The verifier rejects codes outside the closed set, non-literal quotes, role mismatches, unknown ids and missing utterances; rejected codes stay unverified and never count.
- `metrics.py`: all metrics computed in code from verified codes only (reflections per question, % complex, % MI-adherent, change-talk ratio). Sessions with fewer than 20 coded clinician utterances are "brief" (no global scores, only moments).
- `oarsight code` command (default: Spark with low reasoning effort).
- 36 offline tests (10 new: verifier accept/reject, injection-as-data, metrics math and mode boundary, redaction, both coders with a stubbed model).
- Real runs on the fictional consultation (36 utterances) with **both Muse Spark ($0.034) and Muse Spark Open on Baseten (private mode)**: 36/36 verified on both, same "brief" mode, same change-talk ratio (0.36), near-identical code counts.
- Fireworks wired as a second private-mode engine (`--model fireworks`, `accounts/fireworks/models/muse-spark-open`); `oarsight check` passes on all three providers.

## Day 7 — Mon, Nov 2 (continued)

Minimal web interface, written from scratch:

- `web.py`: FastAPI app. Upload an audio file, the pipeline (transcribe → roles/utterances → coding/metrics) runs as a background task, the page polls until done. Same JSON files as the CLI. Session ids are strictly validated; uploads capped at 100 MB.
- `static/index.html`: one page, no framework, in Spanish. Consent checkbox before upload, stage progress, coverage banner, time-scaled two-lane timeline (clinician above, patient below; gray hatch = unverified), metrics, utterance list with code chips, audio player with click-to-seek. Fictional-data and no-medical-advice notices.
- `oarsight serve` command (default http://127.0.0.1:8000).
- 40 offline tests (4 new for the web API). Verified end to end in-process against the fictional session (36 utterances, 36 codes, audio served); JS syntax checked.
- Supervisor (fixed version, single pass): `moments.py` generates up to 8 candidates in code (significant patient utterance + next clinician response, scored); `supervisor.py` picks up to 3 moments and proposes an alternative (≤ 20 words) for each, re-coded by the clinician coder and regenerated at most twice on mismatch. `oarsight supervise` command; moments shown on the page with verified/unverified badges. Real run on the fictional session with Wonder ($0.24): 8 candidates, 3 moments, all 3 alternatives verified on the first attempt.
- 47 offline tests.
- Live process signals on the page: the pipeline reports a `detail` message with real counts at every stage; the page shows an animated stepper (done ✓ / current pulsing), a progress bar, a timestamped activity log, an elapsed timer and a live dot. Honors `prefers-reduced-motion`.
- In-browser recording: the upload card has "upload file" and "record live" tabs; recording uses the microphone with a level meter and timer, then goes through the same pipeline (ffmpeg converts the browser's webm/mp4).
- Moments presentation reworked around MI: summary line ("Tienes N aciertos y M oportunidades"), aciertos first, every moment follows qué pasó → por qué importa → podrías decir with the skill named, why it works and its verification note, plus listen-to-fragment and view-in-transcript links. Strategy recorded as an HTML comment.
- Expert report (`report.py`, Wonder): session pattern, up to 2 strengths with literal quotes (dropped when unverified, falling back to acierto moments), ONE skill chosen by code from the metrics, brief-EM tools in brief mode, and up to 4 conclusions. `oarsight report` command; report shown first on the page. Real run ($0.05): 2/2 strengths verified, grounded conclusions citing real numbers.
- Results split into navigable views (report, moments, timeline, metrics, utterances): sticky nav with pills, prev/next, position counter and hash links; cross-links jump to the right view.
- Clinical typography: IBM Plex Sans (400/500/600/700, latin), self-hosted under `static/fonts/` with its OFL license; tabular numerals for metric values; system sans as fallback.
- 56 offline tests.
