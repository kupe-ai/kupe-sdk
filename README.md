# Kupe Python SDK

Official client for the [Kupe](https://x.kupe.in) voice API.

```bash
pip install kupe
```

Local checkout:

```bash
pip install -e ./kupe-sdk
```

## Quickstart

```python
from kupe import Kupe

client = Kupe()  # KUPE_API_KEY
session = client.realtime.sessions.create(
    name="Priya",
    voice="priya",
    prompt="You collect overdue EMIs. Be warm and brief.",
    greeting="Hi, this is Priya from the bank.",
)
with client.realtime.connect(session) as rt:
    rt.send_text("Hi — remind them EMI is due tomorrow.")
    for event in rt:
        if event.type == "response.output_audio_transcript.done":
            print(event.transcript)
```

Auth is `Authorization: Bearer sk-kupe-...` (or a Supabase JWT). Default base is `https://x.kupe.in`. Env: `KUPE_API_KEY`, optional `KUPE_BASE_URL`.

Pass `name` or `agent_id` (copy it from the agent editor). If `name` is new, Kupe creates the agent with `prompt`, `greeting`, `voice`, and `tools`/`mcp`. If that name already exists in the project, the existing agent is reused and those fields overlay this session. Pass `voice` (name) or `voice_id` — either one.

Every HTTP path is `{base}/v1/...`. Passing `base_url="https://x.kupe.in/v1"` is fine — the client will not drop `/v1`.

When `org_id` / `project_id` are omitted, they are filled from `GET /v1/me`.

## Resources

`client.agents`, `realtime`, `sessions`, `inbound`, `campaigns`, `recipient_lists`, `tools`, `composio`, `analyses`, `databases`, `knowledge_bases`, `phones`, `voices`, `providers`, `logs`, `billing`, `usage`, `orgs`, `projects`.

Realtime audio is PCM16 mono at 24 kHz (`rt.append_audio(pcm)`). Playing the
agent through open speakers next to the mic makes it hear and answer itself —
pass `client.realtime.connect(session, echo_suppression="half_duplex")` to mute
the mic while the agent speaks (no barge-in), or use a headset and keep the
default `"none"`. Voice clone / patch / delete require a user JWT — calling them with an API key raises `JWTRequiredError`.

Payments, credit checkout, and per-service usage breakdown are not included.

See `examples/realtime_text_turn.py`.
