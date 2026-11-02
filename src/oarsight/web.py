"""Web interface: upload audio, run the pipeline, see the timeline and metrics.

One page (no framework) served by FastAPI. Sessions run in a background task;
the page polls until the session is done. All result files are the same JSON
the CLI commands write.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Any

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from . import coding, coverage, metrics, moments, report, supervisor, utterances
from .api import TranscribeClient
from .config import Settings, load_settings
from .llm import make_model
from .roles import assign_roles
from .transcription import transcribe_file
from .usage import UsageLog

STATIC_DIR = Path(__file__).resolve().parent / "static"
SESSION_ID = re.compile(r"^[A-Za-z0-9_-]+$")
MAX_UPLOAD_BYTES = 100 * 1024 * 1024


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    app = FastAPI(title="Oarsight")
    app.state.settings = settings
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    @app.post("/api/sessions")
    async def create_session(
        background: BackgroundTasks, audio: Annotated[UploadFile, File()]
    ) -> dict[str, str]:
        data = await audio.read()
        if not data:
            raise HTTPException(400, "Empty audio file.")
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(400, "Audio is larger than 100 MB.")
        stem = re.sub(r"[^A-Za-z0-9_-]+", "_", Path(audio.filename or "audio").stem) or "audio"
        session_id = f"{stem}_{int(time.time())}"
        session_dir = settings.data_dir / "sessions" / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / f"upload{Path(audio.filename or '').suffix}").write_bytes(data)
        _write_status(session_dir, {"status": "queued", "stage": "transcribing"})
        background.add_task(_run_pipeline, session_dir, session_id, settings)
        return {"id": session_id, "status": "queued"}

    @app.get("/api/sessions/{session_id}")
    def get_session(session_id: str) -> dict[str, Any]:
        session_dir = _session_dir(settings, session_id)
        if not (session_dir / "status.json").exists():
            raise HTTPException(404, "Unknown session.")
        payload: dict[str, Any] = {"id": session_id}
        payload.update(json.loads((session_dir / "status.json").read_text(encoding="utf-8")))
        for name in (
            "coverage",
            "transcript",
            "roles",
            "utterances",
            "coding",
            "metrics",
            "candidates",
            "moments",
            "report",
        ):
            path = session_dir / f"{name}.json"
            if path.exists():
                payload[name] = json.loads(path.read_text(encoding="utf-8"))
        if "report" in payload and payload["report"].get("skill_id") in report.SKILLS:
            payload["report"]["skill"] = report.SKILLS[payload["report"]["skill_id"]]
        return payload

    @app.get("/api/sessions/{session_id}/audio")
    def get_audio(session_id: str) -> FileResponse:
        wav = _session_dir(settings, session_id) / "audio.wav"
        if not wav.exists():
            raise HTTPException(404, "Audio is not ready yet.")
        return FileResponse(wav, media_type="audio/wav")

    return app


def _session_dir(settings: Settings, session_id: str) -> Path:
    if not SESSION_ID.match(session_id):
        raise HTTPException(404, "Unknown session.")
    return settings.data_dir / "sessions" / session_id


def _write_status(session_dir: Path, status: dict[str, Any]) -> None:
    status["updated"] = time.time()
    (session_dir / "status.json").write_text(json.dumps(status, ensure_ascii=False), encoding="utf-8")


def _run_pipeline(session_dir: Path, session_id: str, settings: Settings) -> None:
    """transcribe -> roles/utterances -> coding/metrics -> moments, recording the stage as it goes."""
    usage = UsageLog(settings.data_dir / "usage.jsonl")
    started = time.time()
    try:
        uploads = [p for p in session_dir.iterdir() if p.name.startswith("upload")]
        if not uploads:
            raise RuntimeError("The uploaded audio is missing.")
        _write_status(
            session_dir,
            {
                "status": "running",
                "stage": "transcribing",
                "detail": "Convirtiendo el audio y transcribiendo…",
            },
        )
        client = TranscribeClient(settings.require_meta_key(), usage=usage)
        transcript = transcribe_file(uploads[0], client, session_dir)
        (session_dir / "transcript.json").write_text(transcript.to_json(), encoding="utf-8")
        cov = coverage.assess(transcript)
        (session_dir / "coverage.json").write_text(
            json.dumps(asdict(cov), ensure_ascii=False, default=str), encoding="utf-8"
        )
        if not cov.complete:
            _write_status(
                session_dir,
                {
                    "status": "incomplete",
                    "stage": "transcribing",
                    "detail": f"Solo se transcribió el {cov.fraction:.0%} del habla.",
                    "error": "La transcripción cubre muy poco del audio; esta sesión no se analiza.",
                    "turns": len(transcript.turns),
                    "cost": usage.cost_summary(),
                },
            )
            return

        _write_status(
            session_dir,
            {
                "status": "running",
                "stage": "preparing",
                "detail": f"{len(transcript.turns)} turnos transcritos. Identificando quién es quién…",
                "turns": len(transcript.turns),
            },
        )
        roles = assign_roles(transcript, make_model("spark", settings, usage, reasoning_effort="low"))
        (session_dir / "roles.json").write_text(
            json.dumps(asdict(roles), ensure_ascii=False), encoding="utf-8"
        )
        utts = utterances.build_utterances(transcript, roles)
        utterances.save(utts, session_dir / "utterances.json")

        _write_status(
            session_dir,
            {
                "status": "running",
                "stage": "coding",
                "detail": f"{len(utts)} enunciados. Codificando con el libro MITI…",
                "turns": len(transcript.turns),
                "utterances": len(utts),
            },
        )
        codings, _shown, redacted = coding.code_session(
            utts, make_model("spark", settings, usage, reasoning_effort="low")
        )
        coding.save(codings, session_dir / "coding.json")
        session_metrics = metrics.compute(utts, codings)
        metrics.save(session_metrics, session_dir / "metrics.json")
        verified = sum(1 for c in codings if c.verified)

        _write_status(
            session_dir,
            {
                "status": "running",
                "stage": "supervising",
                "detail": f"{verified}/{len(codings)} códigos verificados. Eligiendo momentos clave…",
                "turns": len(transcript.turns),
                "utterances": len(utts),
                "verified": verified,
            },
        )
        cands = moments.build_candidates(utts, codings)
        moments.save(cands, session_dir / "candidates.json")
        results = supervisor.supervise(cands, utts, codings, make_model("wonder", settings, usage))
        supervisor.save(results, session_dir / "moments.json")

        _write_status(
            session_dir,
            {
                "status": "running",
                "stage": "reporting",
                "detail": f"{len(results)} momentos. Redactando el informe experto…",
                "turns": len(transcript.turns),
                "utterances": len(utts),
                "verified": verified,
            },
        )
        expert = report.build_report(
            utts, codings, session_metrics, cands, results, make_model("wonder", settings, usage)
        )
        report.save(expert, session_dir / "report.json")

        _write_status(
            session_dir,
            {
                "status": "done",
                "stage": "done",
                "detail": f"Listo en {time.time() - started:.0f} s: {len(results)} momentos.",
                "turns": len(transcript.turns),
                "utterances": len(utts),
                "verified": verified,
                "redacted": redacted,
                "cost": usage.cost_summary(),
            },
        )
    except Exception as exc:  # noqa: BLE001 - the page shows whatever failed
        _write_status(session_dir, {"status": "error", "stage": "failed", "error": str(exc)})


app = create_app()
