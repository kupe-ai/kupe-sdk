"""Realtime WebSocket helper.

Audio is PCM16 mono at 24 kHz. Text turns use ``conversation.item.create``
followed by ``response.create``.
"""

from __future__ import annotations

import base64
import json
import threading
import time
from collections.abc import Callable, Iterator
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from kupe._models import RealtimeEvent, RealtimeSession

PCM16_SAMPLE_RATE = 24_000

#: Valid values for ``RealtimeConnection(echo_suppression=...)``.
ECHO_SUPPRESSION_MODES = ("none", "half_duplex")

# Events that mean the agent's audio has stopped playing right now, so the
# echo-suppression gate can reopen immediately instead of waiting out the
# queued playback estimate.
_PLAYBACK_STOP_EVENTS = frozenset(
    {
        "input_audio_buffer.speech_started",
        "response.cancelled",
        "response.canceled",
    }
)


def b64_pcm16_seconds(b64_audio: str, *, sample_rate: int = PCM16_SAMPLE_RATE) -> float:
    """Playback duration of a base64 PCM16-mono payload, without decoding it.

    Used to track how long the agent's audio will still be coming out of the
    speakers: deltas arrive faster than realtime, so the number of bytes
    buffered -- not the arrival time of the last delta -- is what says when
    playback actually ends.
    """
    length = len(b64_audio)
    if length == 0:
        return 0.0
    padding = b64_audio.count("=", max(0, length - 2))
    n_bytes = (length * 3) // 4 - padding
    if n_bytes <= 0:
        return 0.0
    return n_bytes / 2 / float(sample_rate)


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
    """Context manager around the Kupe realtime WebSocket.

    ``echo_suppression`` controls what happens to mic audio while the agent is
    talking:

    ``"none"`` (default)
        Every frame passed to :meth:`append_audio` is sent. Correct when the
        caller already has acoustic echo cancellation -- a headset, a browser
        ``getUserMedia({echoCancellation: true})`` stream, or a phone line.
        Barge-in works.

    ``"half_duplex"``
        Mic frames are dropped while the agent's audio is still playing. Use
        this for open speakers (a laptop running a terminal script), where the
        mic otherwise records the agent and sends its own voice back as user
        speech. **Trade-off: the caller cannot barge in**, because the server
        never hears them until the agent finishes.
    """

    def __init__(
        self,
        url: str,
        *,
        connect_fn: Callable[[str], Any] | None = None,
        echo_suppression: str = "none",
        echo_tail_ms: int = 250,
    ) -> None:
        if echo_suppression not in ECHO_SUPPRESSION_MODES:
            raise ValueError(
                "echo_suppression must be one of "
                f"{list(ECHO_SUPPRESSION_MODES)}, got {echo_suppression!r}"
            )
        self.url = url
        self._connect_fn = connect_fn or _default_connect
        self._ws: Any = None
        self.echo_suppression = echo_suppression
        # Speakers keep ringing for a moment after the last sample, and room
        # reverb outlives that again, so hold the gate shut a little longer.
        self._echo_tail = max(0.0, echo_tail_ms / 1000.0)
        self._playback_lock = threading.Lock()
        self._playback_until = 0.0
        #: Frames replaced with silence by echo suppression (diagnostics).
        self.suppressed_frames = 0

    @classmethod
    def from_session(
        cls,
        session: RealtimeSession | Any,
        *,
        connect_fn: Callable[[str], Any] | None = None,
        echo_suppression: str = "none",
        echo_tail_ms: int = 250,
    ) -> RealtimeConnection:
        secret = _session_secret(session)
        ws_url = _session_ws_url(session)
        return cls(
            build_realtime_ws_url(ws_url, secret),
            connect_fn=connect_fn,
            echo_suppression=echo_suppression,
            echo_tail_ms=echo_tail_ms,
        )

    @property
    def agent_is_speaking(self) -> bool:
        """True while the agent's audio is still expected to be audible.

        Tracked from ``response.output_audio.delta`` sizes as events are
        consumed, so this only advances while something is iterating the
        connection.
        """
        with self._playback_lock:
            return time.monotonic() < self._playback_until

    def _note_event(self, event: RealtimeEvent) -> None:
        """Update the playback estimate that echo suppression gates on."""
        etype = getattr(event, "type", "") or ""
        if etype == "response.output_audio.delta":
            delta = getattr(event, "delta", None)
            if not isinstance(delta, str) or not delta:
                return
            seconds = b64_pcm16_seconds(delta)
            if seconds <= 0:
                return
            now = time.monotonic()
            with self._playback_lock:
                # Chain onto the queued audio rather than onto "now": deltas
                # arrive far faster than realtime, so each one pushes the end
                # of playback further out by its own duration.
                queued_until = self._playback_until - self._echo_tail
                start = queued_until if queued_until > now else now
                self._playback_until = start + seconds + self._echo_tail
        elif etype in _PLAYBACK_STOP_EVENTS:
            with self._playback_lock:
                self._playback_until = 0.0

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

    def append_audio(self, pcm16: bytes, *, force: bool = False) -> bool:
        """Append a PCM16 mono frame (24 kHz) to the input audio buffer.

        Returns ``True`` when the caller's audio was sent and ``False`` when
        echo suppression muted it because the agent is still speaking. A muted
        frame is still sent, as silence, so the server's streaming VAD and STT
        keep receiving a continuous stream. Pass ``force=True`` to send the
        real audio regardless of the gate.
        """
        muted = (
            not force
            and self.echo_suppression == "half_duplex"
            and self.agent_is_speaking
        )
        if muted:
            with self._playback_lock:
                self.suppressed_frames += 1
            # Replace the frame with silence instead of skipping the send.
            # The server runs streaming VAD and STT over a continuous audio
            # stream, so sending nothing stalls turn detection entirely --
            # the agent stops hearing the caller even after it finishes
            # speaking. Silence keeps the stream (and the VAD clock) alive
            # while still not carrying the agent's echoed voice.
            pcm16 = b"\x00" * len(pcm16)
        self.send(
            {
                "type": "input_audio_buffer.append",
                "audio": base64.b64encode(pcm16).decode("ascii"),
            }
        )
        return not muted

    def commit_audio(self) -> None:
        self.send({"type": "input_audio_buffer.commit"})

    def clear_audio(self) -> None:
        self.send({"type": "input_audio_buffer.clear"})

    def create_response(self) -> None:
        self.send({"type": "response.create"})

    def cancel(self) -> None:
        with self._playback_lock:
            self._playback_until = 0.0
        self.send({"type": "response.cancel"})

    def __iter__(self) -> Iterator[RealtimeEvent]:
        if self._ws is None:
            raise RuntimeError("Realtime connection is not open. Use as a context manager.")
        for raw in self._ws:
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            if not raw:
                continue
            event = RealtimeEvent.model_validate(json.loads(raw))
            self._note_event(event)
            yield event
