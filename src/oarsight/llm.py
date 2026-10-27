"""Interchangeable language-model backends.

Every analysis stage asks a `Model` for JSON. The same stage can run on Muse Wonder or Muse Spark through Meta Model
API, or on Muse Spark Open (open weights) through Baseten, which is Oarsight's private mode.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .api import ChatClient, baseten_client
from .config import SPARK, SPARK_OPEN_BASETEN, WONDER, Settings
from .usage import UsageLog


@dataclass
class Model:
    name: str
    client: ChatClient
    model_id: str
    reasoning_effort: str | None = None

    def json(self, stage: str, system: str, user: str) -> Any:
        return self.client.chat_json(stage, self.model_id, system, user, reasoning_effort=self.reasoning_effort)


BACKENDS = ("wonder", "spark", "spark-open")


def make_model(name: str, settings: Settings, usage: UsageLog | None = None, reasoning_effort: str | None = None) -> Model:
    """Build a model by short name: 'wonder', 'spark' (Meta Model API) or 'spark-open' (Baseten, private mode)."""
    if name == "wonder":
        return Model(name, ChatClient(settings.require_meta_key(), usage=usage), WONDER, reasoning_effort)
    if name == "spark":
        return Model(name, ChatClient(settings.require_meta_key(), usage=usage), SPARK, reasoning_effort)
    if name == "spark-open":
        # Muse Spark Open always reasons; it does not take a reasoning_effort parameter here.
        return Model(name, baseten_client(settings.require_baseten_key(), usage=usage), SPARK_OPEN_BASETEN, None)
    raise ValueError(f"Unknown model backend {name!r}; choose one of {BACKENDS}")
