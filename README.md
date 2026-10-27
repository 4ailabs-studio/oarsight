# Oarsight

**AI supervision for motivational interviewing.**

Oarsight listens to a recorded clinical consultation and gives the clinician verified feedback on their communication: how they used motivational interviewing (MI), the key moments, what they could say instead, targeted voice practice with a simulated patient, and a briefing for the next visit with the same patient.

> **Status:** in active development during the hackathon. This README describes the design; code is added day by day (see the [build log](docs/BUILD_LOG.md)).

## Hackathon submission

| | |
|---|---|
| Event | [Meta Global AI Developer Hackathon](https://cerebralvalley.ai/e/meta-ai-developer-hackathon), Oct 26 – Nov 4, 2026 |
| Track | Indie Developer |
| Problem statement | **Build for Your World**: a physician building the feedback tool clinicians in chronic care don't have |
| Team | Miguel Ojeda Rios (solo) |
| Meta models | Muse Voice Transcribe, Muse Wonder, Muse Spark (Meta Model API); Muse Spark Open (open weights) |
| Demo video (3 min) | *Added before submission* |

### What was built during the hackathon

Everything in this repository was written during the event. The [build log](docs/BUILD_LOG.md) lists, day by day, what was added, and the commit history shows when.

**Prior-work disclosure.** Before the kickoff, the author researched the problem, sketched the design, and ran small throwaway experiments against the Meta Model API to check feasibility (transcription, speaker separation, coding prompts). None of that code is in this repository; everything here was written from scratch during the event. The repository itself was created on October 26 a few minutes before the kickoff, with only this README and configuration files.

## The problem

Motivational interviewing helps patients with chronic disease change behavior; a meta-analysis found it lowers HbA1c in type 2 diabetes ([Berhe et al., 2020](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7584232/)). Clinicians improve at MI when they get feedback and coaching on their own sessions, not from workshops alone ([Miller et al., 2004](https://motivationalinterviewing.org/node/3856)). That feedback depends on experts coding sessions by hand, which is slow and expensive, so most clinicians never receive it, especially in Spanish-speaking primary care.

## What Oarsight does

1. **Feedback on a consultation.** One skill to work on next time, two strengths with quotes, and up to three key moments: what the patient said, how the clinician answered, and a better way to phrase it, each linked to the audio.
2. **Targeted practice.** A voice-based simulated patient replays the clinician's weakest moments. The patient's resistance is tracked in code, so it does not open up for free.
3. **Next-visit briefing.** What matters to the patient in their own words, what to avoid, open topics, and how the patient's change talk evolves across visits.

### What Oarsight is not

Oarsight is a **communication-skills training tool for clinicians**. It evaluates how the clinician communicates. It does **not** diagnose, assess the patient's health, recommend treatments, or give medical or mental-health advice to anyone. Clinical decisions stay with the clinician.

## How it works

| Step | Model |
|---|---|
| Transcription with speaker labels and turn timestamps | Muse Voice Transcribe |
| Speaker roles (clinician, patient) and term checks, without rewriting the transcript | Muse Wonder |
| Utterance-level coding of clinician behaviors and patient change and sustain talk | Muse Spark |
| Skeptic reviewer, supervisor and next-visit agents with tool calling | Muse Wonder |
| Simulated patient for voice practice | Muse Wonder + Muse Voice Transcribe (realtime) |
| Private mode for confidential sessions | Muse Spark Open, served on partner endpoints or self-hosted |

**Design principle: the model proposes, the code decides.** Every quote is checked against the transcript, metrics are computed in code, and every suggested phrasing is re-coded to confirm it is the skill it claims to be. Segments that cannot be verified are shown as unverified and never count toward feedback. The full list, with what is already implemented, is in [docs/GUARDRAILS.md](docs/GUARDRAILS.md).

## Evaluation plan

- Utterance-level agreement with expert annotations on public MI datasets (see *Third-party data* below).
- Ablations: single prompt vs. specialized coders, with and without the skeptic reviewer, Spark vs. Wonder, hosted vs. open-weight model.
- Leniency bias, run-to-run stability, cost, and latency per session.

## Data and privacy

- This project uses **only fictional or role-played consultations**. No real patient data is stored in this repository, used in development, or shown in the demo.
- Audio, transcripts, and evaluation data are excluded from git (`.gitignore`).
- Any real-world use would require the patient's informed consent before recording.

## Third-party data and references

- **AnnoMI** (Wu et al., ICASSP 2022), a dataset of expert-annotated MI demonstration transcripts released for research. It is used only for evaluation, is **not redistributed** in this repository, and is downloaded separately from [its official repository](https://github.com/uccollab/AnnoMI). Please cite the original paper if you use it.
- **MITI 4.2.1** (Moyers, Manuel and Ernst). Oarsight's coding categories follow the behavior types described in the MITI. The codebook in this project is written in our own words; no text from the manual is reproduced.
## Setup

Requires [uv](https://docs.astral.sh/uv/) and [ffmpeg](https://ffmpeg.org/).

```bash
cp .env.example .env          # then add your MODEL_API_KEY (and BASETEN_API_KEY for private mode)
uv sync
uv run oarsight check         # verify keys and connectivity
uv run oarsight transcribe consultation.mp3
uv run pytest                 # tests run offline
```

`transcribe` prints the transcript with speaker labels and timestamps, checks coverage, and exits with code 2 if the transcript misses too much of the detected speech. Session files are written to `datos/`, which is never committed.

## License

[MIT](LICENSE)
