"""Cost accounting and an append-only log of every model call.

Every call is recorded with its stage, model, latency, tokens and estimated cost. The log feeds the
evaluation (cost and latency per session) and keeps spending visible against the hackathon credits.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

# USD per 1M tokens: (input, output, cached input). Source: Meta Model API pricing page, Oct 2026.
TOKEN_PRICES: dict[str, tuple[float, float, float]] = {
    "muse-wonder-1.0": (4.00, 20.00, 0.20),
    "muse-spark-1.3": (1.25, 4.25, 0.15),
    "muse-spark-1.2": (1.25, 4.25, 0.15),
}
VOICE_TRANSCRIBE_USD_PER_HOUR = 0.18


@dataclass
class CallRecord:
    stage: str
    model: str
    seconds: float
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    cached_tokens: int = 0
    audio_seconds: float = 0.0
    cost_usd: float | None = None
    timestamp: float = field(default_factory=time.time)


def token_cost(model: str, input_tokens: int, output_tokens: int, cached_tokens: int = 0) -> float | None:
    """Estimated USD cost of a token-billed call, or None if the model has no known price."""
    prices = TOKEN_PRICES.get(model)
    if prices is None:
        return None
    price_in, price_out, price_cached = prices
    uncached = max(input_tokens - cached_tokens, 0)
    return (uncached * price_in + cached_tokens * price_cached + output_tokens * price_out) / 1_000_000


def audio_cost(seconds: float) -> float:
    """Voice Transcribe bills processed audio in whole seconds, rounded down."""
    return int(seconds) / 3600 * VOICE_TRANSCRIBE_USD_PER_HOUR


class UsageLog:
    """Collects call records in memory and appends them to a JSONL file."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self.records: list[CallRecord] = []

    def add(self, record: CallRecord) -> None:
        self.records.append(record)
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")

    @property
    def total_cost(self) -> float:
        return sum(r.cost_usd or 0.0 for r in self.records)

    def cost_summary(self) -> str:
        """Known cost, and a note when some calls have no known price (e.g. Baseten credits)."""
        unpriced = sum(1 for r in self.records if r.cost_usd is None)
        text = f"${self.total_cost:.4f}"
        if unpriced:
            text += f" + {unpriced} call(s) without a known price (billed by the provider)"
        return text
