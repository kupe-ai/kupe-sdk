from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def parse(value: Any) -> Any:
    """Wrap dicts as :class:`KupeObject` so nested fields are attributes."""
    if isinstance(value, KupeObject):
        return value
    if isinstance(value, Mapping):
        return KupeObject(value)
    if isinstance(value, list):
        return [parse(item) for item in value]
    return value


class KupeObject:
    """Attribute- and dict-accessible API payload."""

    def __init__(self, data: Mapping[str, Any] | None = None, **extra: Any) -> None:
        payload = dict(data or {})
        payload.update(extra)
        object.__setattr__(self, "_data", payload)
        for key, value in payload.items():
            object.__setattr__(self, key, parse(value))

    def __repr__(self) -> str:
        return f"KupeObject({self._data!r})"

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def __contains__(self, key: object) -> bool:
        return key in self._data

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def to_dict(self) -> dict[str, Any]:
        return dict(self._data)

    def model_dump(self) -> dict[str, Any]:
        return self.to_dict()


class RealtimeEvent(BaseModel):
    """A server event from the realtime WebSocket."""

    model_config = ConfigDict(extra="allow")

    type: str = ""

    def __getitem__(self, key: str) -> Any:
        extra = self.__pydantic_extra__ or {}
        if key in extra:
            return extra[key]
        return getattr(self, key)


class RealtimeClientSecret(BaseModel):
    model_config = ConfigDict(extra="allow")

    value: str
    expires_at: int | None = None


class RealtimeSession(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = ""
    object: str = "realtime.session"
    model: str = "kupe-realtime"
    modalities: list[str] = Field(default_factory=lambda: ["audio", "text"])
    instructions: str = ""
    voice: str = ""
    input_audio_format: str = "pcm16"
    output_audio_format: str = "pcm16"
    tools: list[dict[str, Any]] = Field(default_factory=list)
    client_secret: RealtimeClientSecret
    websocket_url: str
    session_id: str | None = None
