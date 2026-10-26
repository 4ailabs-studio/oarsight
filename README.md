# Oarsight

**AI supervision for motivational interviewing.**

Oarsight listens to a clinical consultation and gives the clinician verified feedback on how they used motivational interviewing (MI): the key moments, what they could say instead, targeted voice practice with a simulated patient, and a briefing for the next visit with the same patient.

Built with Meta Model API for the [Meta Global AI Developer Hackathon](https://cerebralvalley.ai/e/meta-ai-developer-hackathon) (October 26 – November 4, 2026), Indie track.

> **Status:** in active development during the hackathon. This README describes the design; code lands over the coming days.

## The problem

Motivational interviewing helps patients with chronic disease change behavior; a meta-analysis found it lowers HbA1c in type 2 diabetes ([Berhe et al., 2020](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7584232/)). Clinicians get better at MI when they receive feedback and coaching on real sessions, not from workshops alone ([Miller et al., 2004](https://motivationalinterviewing.org/node/3856)). That feedback depends on coding sessions by hand with the MITI manual, which is slow and expensive, so most clinicians never get it, especially in Spanish-speaking primary care.

## What Oarsight does

1. **Feedback on a real consultation.** One skill to work on next time, two strengths with quotes, and up to three key moments: what the patient said, what the clinician answered, and a better alternative, each linked to the audio.
2. **Targeted practice.** A voice-based simulated patient replays the clinician's weakest moments, with resistance tracked in code so the patient doesn't open up for free.
3. **Next-visit briefing.** What matters to the patient in their own words, what to avoid, open topics, and how the patient's change talk evolves across visits.

## How it works

| Step | Meta model |
|---|---|
| Transcription with speaker labels and turn timestamps | Muse Voice Transcribe |
| Speaker roles (clinician, patient) and term checks, without rewriting the transcript | Muse Wonder |
| Utterance-level MI coding (MITI 4.2.1 behaviors, patient change and sustain talk) | Muse Spark |
| Skeptic reviewer, supervisor and next-visit agents with tool calling | Muse Wonder |
| Simulated patient for voice practice | Muse Wonder + Muse Voice Transcribe (realtime) |
| Private mode for confidential sessions | Muse Spark Open (self-hosted) |

**Design principle: the model proposes, the code decides.** Every quote is checked against the transcript, metrics are computed in code, and every suggested alternative is re-coded to confirm it is the MI skill it claims to be. Segments that cannot be verified are shown as unverified and never count toward feedback.

## Evaluation plan

- Utterance-level agreement with expert annotations on [AnnoMI](https://github.com/uccollab/AnnoMI) (English) and, if available, MIDAS (Spanish).
- Ablations: single prompt vs. specialized coders, with and without the skeptic reviewer, Spark vs. Wonder, hosted vs. open-weight model.
- Leniency bias, run-to-run stability, cost, and latency per session.

## Data notice

This project uses **only fictional or role-played consultations**. No real patient data is stored in this repository or used in the demo. Oarsight is a training and decision-support tool for clinicians; it does not give medical advice.

## Setup

```bash
cp .env.example .env   # then add your MODEL_API_KEY
```

More setup instructions will be added as the code lands.
