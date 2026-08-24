from __future__ import annotations

from typing import Any

from kupe.resources._base import APIResource, drop_none


class LogsResource(APIResource):
    """Sessions, transcripts, recordings, and tool-call events.

    There is no dedicated logs API; this surface maps the read endpoints.
    """

    def sessions(
        self,
        *,
        org_id: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Any:
        org_id = self._org(org_id)
        return self._get(f"orgs/{org_id}/sessions", params=drop_none({"limit": limit, "offset": offset}))

    def transcript(self, session_id: str) -> Any:
        return self._get(f"sessions/{session_id}/transcript")

    def recording(self, session_id: str) -> Any:
        return self._get(f"sessions/{session_id}/recording")

    def recordings(
        self,
        *,
        org_id: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Any:
        org_id = self._org(org_id)
        return self._get(f"orgs/{org_id}/recordings", params=drop_none({"limit": limit, "offset": offset}))

    def playback_url(self, recording_id: str) -> Any:
        return self._get(f"recordings/{recording_id}/playback-url")

    def tool_call_events(
        self,
        *,
        org_id: str | None = None,
        agent_id: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Any:
        org_id = self._org(org_id)
        return self._get(
            f"orgs/{org_id}/tool-call-events",
            params=drop_none({"agent_id": agent_id, "limit": limit, "offset": offset}),
        )

    def tool_call_stats(self, agent_id: str, *, org_id: str | None = None) -> Any:
        org_id = self._org(org_id)
        return self._get(f"orgs/{org_id}/agents/{agent_id}/tool-call-stats")
