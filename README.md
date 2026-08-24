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
session = client.realtime.sessions.create(agent_id="agt_...", voice="priya")
with client.realtime.connect(session) as rt:
    rt.send_text("Hi — remind them EMI is due tomorrow.")
    for event in rt:
        if event.type == "response.output_audio_transcript.done":
            print(event.transcript)
```

Auth is `Authorization: Bearer sk-kupe-...` (or a Supabase JWT). Default base is `https://x.kupe.in`. Env: `KUPE_API_KEY`, optional `KUPE_BASE_URL`.

Every HTTP path is `{base}/v1/...`. Passing `base_url="https://x.kupe.in/v1"` is fine — the client will not drop `/v1`.

When `org_id` / `project_id` are omitted, they are filled from `GET /v1/me`.

## Resources

`client.agents`, `realtime`, `sessions`, `inbound`, `campaigns`, `recipient_lists`, `tools`, `composio`, `analyses`, `databases`, `knowledge_bases`, `phones`, `voices`, `providers`, `logs`, `billing`, `usage`, `orgs`, `projects`.

Realtime audio is PCM16 mono at 24 kHz (`rt.append_audio(pcm)`). Voice clone / patch / delete require a user JWT — calling them with an API key raises `JWTRequiredError`.

Payments, credit checkout, and per-service usage breakdown are not included.

See `examples/realtime_text_turn.py`.
