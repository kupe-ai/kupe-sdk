"""Realtime WebSocket helper.

Audio is PCM16 mono at 24 kHz. Text turns use ``conversation.item.create``
followed by ``response.create``.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Callable, Iterator
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from kupe._models import RealtimeEvent, RealtimeSession

PCM16_SAMPLE_RATE = 24_000


def _session_secret(session: RealtimeSession | Any) -> str:
    secret = getattr(session, "client_secret", None)
    if secret is None and isinstance(session, dict):
        secret = session.get("client_secret")
    if isinstance(secret, dict):
        return str(secret["value"])
    value = getattr(secret, "value", None)
    if value is None:
        raise ValueError("session is missing client_secret.value")
    return str(value)


def _session_ws_url(session: RealtimeSession | Any) -> str:
    url = getattr(session, "websocket_url", None)
    if url is None and isinstance(session, dict):
        url = session.get("websocket_url")
    if not url:
        raise ValueError("session is missing websocket_url")
    return str(url)


def build_realtime_ws_url(
    websocket_url: str,
    client_secret: str,
    *,
    model: str = "kupe-realtime",
) -> str:
    parsed = urlparse(websocket_url)
    query = parse_qs(parsed.query)
    query.setdefault("model", [model])
    query.setdefault("client_secret", [client_secret])
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))


def _default_connect(url: str) -> Any:
    from websockets.sync.client import connect

    return connect(url)


class RealtimeConnection:
    """Context manager around the Kupe realtime WebSocket."""

    def __init__(
        self,
        url: str,
        *,
        connect_fn: Callable[[str], Any] | None = None,
    ) -> None:
        self.url = url
        self._connect_fn = connect_fn or _default_connect
        self._ws: Any = None

    @classmethod
    def from_session(
        cls,
        session: RealtimeSession | Any,
        *,
        connect_fn: Callable[[str], Any] | None = None,
    ) -> RealtimeConnection:
        secret = _session_secret(session)
        ws_url = _session_ws_url(session)
        return cls(build_realtime_ws_url(ws_url, secret), connect_fn=connect_fn)

    def __enter__(self) -> RealtimeConnection:
        self._ws = self._connect_fn(self.url)
        return self

    def __exit__(self, *exc: object) -> None:
        ws = self._ws
        self._ws = None
        if ws is None:
            return
        close = getattr(ws, "close", None)
        if close is not None:
            close()

    def send(self, event: dict[str, Any]) -> None:
        if self._ws is None:
            raise RuntimeError("Realtime connection is not open. Use as a context manager.")
        self._ws.send(json.dumps(event))

    def send_text(self, text: str) -> None:
        self.send(
            {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": text}],
                },
            }
        )
        self.send({"type": "response.create"})

    def append_audio(self, pcm16: bytes) -> None:
        """Append a PCM16 mono frame (24 kHz) to the input audio buffer."""
        self.send(
            {
                "type": "input_audio_buffer.append",
                "audio": base64.b64encode(pcm16).decode("ascii"),
            }
        )

    def commit_audio(self) -> None:
        self.send({"type": "input_audio_buffer.commit"})

    def clear_audio(self) -> None:
        self.send({"type": "input_audio_buffer.clear"})

    def create_response(self) -> None:
        self.send({"type": "response.create"})

    def cancel(self) -> None:
        self.send({"type": "response.cancel"})

    def __iter__(self) -> Iterator[RealtimeEvent]:
        if self._ws is None:
            raise RuntimeError("Realtime connection is not open. Use as a context manager.")
        for raw in self._ws:
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            if not raw:
                continue
            yield RealtimeEvent.model_validate(json.loads(raw))
