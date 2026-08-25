from __future__ import annotations

from typing import Any

from kupe._models import RealtimeSession
from kupe.resources._base import APIResource


class RealtimeSessionsResource(APIResource):
    def create(
        self,
        *,
        agent_id: str | None = None,
        id: str | None = None,
        name: str | None = None,
        voice: str | None = None,
        voice_id: str | None = None,
        prompt: str | None = None,
        instructions: str | None = None,
        greeting: str | None = None,
        greetings: str | None = None,
        tools: list | None = None,
        mcp: dict | list | None = None,
        org_id: str | None = None,
        project_id: str | None = None,
        variables: dict[str, str] | None = None,
        **extra: Any,
    ) -> RealtimeSession:
        body: dict[str, Any] = {**extra}
        resolved_id = agent_id or id
        if resolved_id is not None:
            body["agent_id"] = resolved_id
        if name is not None:
            body["name"] = name
        if voice is not None:
            body["voice"] = voice
        if voice_id is not None:
            body["voice_id"] = voice_id
        if prompt is not None:
            body["prompt"] = prompt
        if instructions is not None:
            body["instructions"] = instructions
        if greeting is not None:
            body["greeting"] = greeting
        if greetings is not None:
            body["greetings"] = greetings
        if tools is not None:
            body["tools"] = tools
        if mcp is not None:
            body["mcp"] = mcp
        if org_id is not None:
            body["org_id"] = org_id
        if project_id is not None:
            body["project_id"] = project_id
        if variables is not None:
            body["variables"] = variables
        payload = self._post("realtime/sessions", json=body)
        data = payload.to_dict() if hasattr(payload, "to_dict") else payload
        return RealtimeSession.model_validate(data)


class RealtimeResource(APIResource):
    def __init__(self, client: Any) -> None:
        super().__init__(client)
        self.sessions = RealtimeSessionsResource(client)

    def connect(self, session: RealtimeSession | Any, **kwargs: Any):
        from kupe.realtime import RealtimeConnection

        return RealtimeConnection.from_session(session, connect_fn=kwargs.get("connect_fn"))
