"""Thin clients for Meta Model API and for OpenAI-compatible endpoints (Baseten).

Design notes:
- Retries with exponential backoff and jitter on 429 and 5xx, honoring Retry-After.
- Every call is logged with tokens, latency and estimated cost (see usage.py).
- Chat calls request JSON output; callers validate the content themselves.
"""

from __future__ import annotations

import json
import random
import time
from pathlib import Path
from typing import Any

import httpx

from .config import BASETEN_BASE_URL, META_BASE_URL, VOICE_TRANSCRIBE
from .usage import CallRecord, UsageLog, audio_cost, token_cost

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class ApiError(RuntimeError):
    def __init__(self, status: int, body: str) -> None:
        super().__init__(f"HTTP {status}: {body[:500]}")
        self.status = status
        self.body = body


def _backoff_seconds(attempt: int, retry_after: str | None) -> float:
    if retry_after:
        try:
            return float(retry_after)
        except ValueError:
            pass
    return min(0.5 * 2**attempt, 20.0) + random.uniform(0, 0.5)


def parse_json_content(text: str) -> Any:
    """Parse a model's JSON answer, tolerating a surrounding Markdown code fence."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else ""
        cleaned = cleaned.rsplit("```", 1)[0]
    return json.loads(cleaned)


class ChatClient:
    """OpenAI-compatible chat completions client (Meta Model API or Baseten)."""

    def __init__(
        self,
        api_key: str,
        base_url: str = META_BASE_URL,
        usage: UsageLog | None = None,
        timeout: float = 300.0,
        max_retries: int = 4,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._http = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
            transport=transport,
        )
        self.usage = usage or UsageLog()
        self.max_retries = max_retries

    def _post(self, path: str, **kwargs: Any) -> httpx.Response:
        for attempt in range(self.max_retries + 1):
            response = self._http.post(path, **kwargs)
            if response.status_code < 400:
                return response
            if response.status_code in RETRYABLE_STATUS and attempt < self.max_retries:
                time.sleep(_backoff_seconds(attempt, response.headers.get("retry-after")))
                continue
            raise ApiError(response.status_code, response.text)
        raise AssertionError("unreachable")

    def chat(
        self,
        stage: str,
        model: str,
        messages: list[dict[str, Any]],
        *,
        reasoning_effort: str | None = None,
        json_output: bool = True,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run one chat completion and return the raw response, logging usage."""
        body: dict[str, Any] = {"model": model, "messages": messages}
        if json_output:
            body["response_format"] = {"type": "json_object"}
        if reasoning_effort:
            body["reasoning_effort"] = reasoning_effort
        if extra:
            body.update(extra)
        started = time.monotonic()
        data = self._post("/chat/completions", json=body).json()
        usage = data.get("usage") or {}
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0) or 0
        self.usage.add(
            CallRecord(
                stage=stage,
                model=model,
                seconds=round(time.monotonic() - started, 2),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                reasoning_tokens=(usage.get("completion_tokens_details") or {}).get("reasoning_tokens", 0) or 0,
                cached_tokens=cached,
                cost_usd=token_cost(model, input_tokens, output_tokens, cached),
            )
        )
        return data

    def chat_json(self, stage: str, model: str, system: str, user: str, **kwargs: Any) -> Any:
        """Chat with a system and a user message and return the parsed JSON answer."""
        data = self.chat(
            stage, model, [{"role": "system", "content": system}, {"role": "user", "content": user}], **kwargs
        )
        return parse_json_content(data["choices"][0]["message"]["content"])

    def list_models(self) -> list[str]:
        response = self._http.get("/models")
        if response.status_code >= 400:
            raise ApiError(response.status_code, response.text)
        return [m["id"] for m in response.json().get("data", [])]


class TranscribeClient:
    """Muse Voice Transcribe file endpoint: POST /v1/asr/transcribe (WAV, mono, 16-bit PCM, max 10 min)."""

    def __init__(
        self,
        api_key: str,
        usage: UsageLog | None = None,
        timeout: float = 600.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._http = httpx.Client(
            base_url=META_BASE_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
            transport=transport,
        )
        self.usage = usage or UsageLog()

    def transcribe(
        self,
        wav_path: Path,
        *,
        mode: str = "DIARIZATION",
        language_bias: list[str] | None = None,
        keywords: list[str] | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        settings: dict[str, Any] = {"mode": mode, "model": VOICE_TRANSCRIBE, "audioEncoding": "WAV"}
        if language_bias:
            settings["languageBias"] = language_bias
        if keywords:
            settings["keywords"] = keywords
        started = time.monotonic()
        with wav_path.open("rb") as audio:
            response = self._http.post(
                "/asr/transcribe",
                params={"sessionId": session_id} if session_id else None,
                files={
                    "request": (None, json.dumps(settings), "application/json"),
                    "audio": (wav_path.name, audio, "audio/wav"),
                },
            )
        if response.status_code >= 400:
            raise ApiError(response.status_code, response.text)
        data = response.json()
        audio_seconds = (data.get("audioDurationMs") or 0) / 1000
        self.usage.add(
            CallRecord(
                stage="transcribe",
                model=VOICE_TRANSCRIBE,
                seconds=round(time.monotonic() - started, 2),
                audio_seconds=audio_seconds,
                cost_usd=audio_cost(audio_seconds),
            )
        )
        return data


def baseten_client(api_key: str, usage: UsageLog | None = None) -> ChatClient:
    """Chat client for Muse Spark Open served by Baseten (OpenAI-compatible)."""
    return ChatClient(api_key, base_url=BASETEN_BASE_URL, usage=usage)
