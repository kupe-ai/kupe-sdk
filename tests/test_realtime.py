from __future__ import annotations

import json

import httpx
import pytest

from kupe import JWTRequiredError
from kupe.realtime import PCM16_SAMPLE_RATE
from tests.conftest import mock_client

FAKE_JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.sig"


class FakeWS:
    def __init__(self, incoming: list[str] | None = None) -> None:
        self.sent: list[str] = []
        self.incoming = incoming or []

    def send(self, data: str) -> None:
        self.sent.append(data)

    def close(self) -> None:
        pass

    def __iter__(self):
        return iter(self.incoming)


def test_realtime_session_create_path() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "id": "sess_1",
                "client_secret": {"value": "eph_secret", "expires_at": 1},
                "websocket_url": "wss://x.kupe.in/v1/realtime",
                "voice": "priya",
            },
        )

    client = mock_client(handler)
    session = client.realtime.sessions.create(agent_id="agt_1", voice="priya")
    assert str(captured[0].url) == "https://x.kupe.in/v1/realtime/sessions"
    assert json.loads(captured[0].content) == {"agent_id": "agt_1", "voice": "priya"}
    assert session.client_secret.value == "eph_secret"
    assert session.websocket_url.endswith("/v1/realtime")
    client.close()


def test_realtime_session_create_voice_id() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "id": "sess_1",
                "client_secret": {"value": "eph_secret", "expires_at": 1},
                "websocket_url": "wss://x.kupe.in/v1/realtime",
                "voice": "priya",
            },
        )

    client = mock_client(handler)
    client.realtime.sessions.create(agent_id="agt_1", voice_id="pub-1")
    assert json.loads(captured[0].content) == {"agent_id": "agt_1", "voice_id": "pub-1"}
    client.close()


def test_realtime_session_create_by_name() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "id": "sess_1",
                "agent_id": "new-agt",
                "client_secret": {"value": "eph_secret", "expires_at": 1},
                "websocket_url": "wss://x.kupe.in/v1/realtime",
                "voice": "priya",
            },
        )

    client = mock_client(handler)
    session = client.realtime.sessions.create(
        name="Priya",
        voice="priya",
        prompt="Be brief.",
        greeting="Hi.",
        tools=[{"type": "function", "name": "lookup_emi"}],
    )
    assert json.loads(captured[0].content) == {
        "name": "Priya",
        "voice": "priya",
        "prompt": "Be brief.",
        "greeting": "Hi.",
        "tools": [{"type": "function", "name": "lookup_emi"}],
    }
    assert session.agent_id == "new-agt"
    client.close()


def test_realtime_text_and_audio_and_events() -> None:
    fake = FakeWS(
        incoming=[
            json.dumps({"type": "session.created"}),
            json.dumps({"type": "response.output_audio_transcript.done", "transcript": "hello"}),
        ]
    )

    def connect_fn(url: str) -> FakeWS:
        fake.url = url  # type: ignore[attr-defined]
        return fake

    session = {
        "client_secret": {"value": "eph", "expires_at": 1},
        "websocket_url": "wss://x.kupe.in/v1/realtime",
    }
    client = mock_client(lambda r: httpx.Response(500))
    with client.realtime.connect(session, connect_fn=connect_fn) as rt:
        assert "client_secret=eph" in rt.url
        assert "model=kupe-realtime" in rt.url
        rt.send_text("Hi there")
        rt.append_audio(b"\x00\x01" * 4)
        events = list(rt)

    sent = [json.loads(m) for m in fake.sent]
    assert sent[0]["type"] == "conversation.item.create"
    assert sent[0]["item"]["content"][0]["text"] == "Hi there"
    assert sent[1] == {"type": "response.create"}
    assert sent[2]["type"] == "input_audio_buffer.append"
    assert events[1].type == "response.output_audio_transcript.done"
    assert events[1].transcript == "hello"
    assert PCM16_SAMPLE_RATE == 24_000
    client.close()


def test_voice_clone_rejects_api_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("must not hit the network")

    client = mock_client(handler)
    with pytest.raises(JWTRequiredError, match="user JWT"):
        client.voices.clone(name="Mine", sample=b"RIFF")
    with pytest.raises(JWTRequiredError):
        client.voices.delete("voice_1")
    with pytest.raises(JWTRequiredError):
        client.voices.update("voice_1", name="x")
    client.close()


def test_voice_clone_with_jwt_posts_multipart() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(201, json={"id": "voice_1", "name": "Mine"})

    client = mock_client(handler, api_key=FAKE_JWT)
    out = client.voices.clone(name="Mine", sample=b"audio-bytes")
    assert captured[0].url.path == "/v1/voices/clone"
    assert captured[0].method == "POST"
    content_type = captured[0].headers["content-type"]
    assert "multipart/form-data" in content_type
    assert out.id == "voice_1"
    client.close()
