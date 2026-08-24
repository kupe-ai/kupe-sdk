from __future__ import annotations

from typing import Any

from kupe.resources._base import APIResource


class ProvidersResource(APIResource):
    def list(self) -> Any:
        """STT / LLM / TTS catalog (``GET /v1/providers``)."""
        return self._get("providers")
