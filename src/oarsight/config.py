"""Settings loaded from the environment (and a local .env file that is never committed)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

META_BASE_URL = "https://api.meta.ai/v1"
BASETEN_BASE_URL = "https://inference.baseten.co/v1"

# Model IDs
WONDER = "muse-wonder-1.0"
SPARK = "muse-spark-1.3"  # Standard mode only: our content must never be used for training.
VOICE_TRANSCRIBE = "muse-voice-transcribe-1.0"
SPARK_OPEN_BASETEN = "meta-models/muse-spark-open-1026"  # the only model the hackathon Baseten key accepts


class MissingKeyError(RuntimeError):
    """Raised when a required API key is not configured."""


@dataclass(frozen=True)
class Settings:
    meta_api_key: str | None
    baseten_api_key: str | None
    data_dir: Path

    def require_meta_key(self) -> str:
        if not self.meta_api_key:
            raise MissingKeyError("MODEL_API_KEY is not set. Copy .env.example to .env and add your key.")
        return self.meta_api_key

    def require_baseten_key(self) -> str:
        if not self.baseten_api_key:
            raise MissingKeyError("BASETEN_API_KEY is not set in .env.")
        return self.baseten_api_key


def load_settings(env_file: Path | None = None) -> Settings:
    """Read keys from the process environment, falling back to a .env file."""
    load_dotenv(env_file or Path.cwd() / ".env", override=False)
    return Settings(
        meta_api_key=os.environ.get("MODEL_API_KEY") or None,
        baseten_api_key=os.environ.get("BASETEN_API_KEY") or None,
        data_dir=Path(os.environ.get("OARSIGHT_DATA_DIR", "datos")),
    )
