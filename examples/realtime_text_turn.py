"""Mint a Kupe realtime session and run one text turn over WebSocket.

Requires:
  pip install -e ./kupe-sdk
  export KUPE_API_KEY=sk-kupe-...
"""

from __future__ import annotations

import os

from kupe import Kupe

AGENT_ID = os.environ.get("KUPE_AGENT_ID", "agt_collections_demo")
VOICE = os.environ.get("KUPE_VOICE", "tripti")

client = Kupe()  # KUPE_API_KEY, optional KUPE_BASE_URL
session = client.realtime.sessions.create(agent_id=AGENT_ID, voice=VOICE)
print(f"session ok — voice={VOICE} ws={session.websocket_url}")

with client.realtime.connect(session) as rt:
    rt.send_text("Hi Tripti — remind this customer their EMI is due tomorrow.")
    for event in rt:
        if event.type == "response.output_audio.delta":
            # event.delta → base64 PCM16 — enqueue on your audio player
            continue
        if event.type == "response.output_audio_transcript.done":
            print("agent:", event.transcript)
            continue
        if event.type == "error":
            print("error:", event)
            continue
        if event.type in (
            "session.created",
            "response.created",
            "response.done",
            "response.output_audio.done",
        ):
            print("event:", event.type)
