from __future__ import annotations

from typing import Any

from kupe.resources._base import APIResource, drop_none


class SessionsResource(APIResource):
    def create(self, **body: Any) -> Any:
        org_id, project_id = self._scope(body.get("org_id"), body.get("project_id"))
        body.setdefault("org_id", org_id)
        body.setdefault("project_id", project_id)
        return self._post("sessions", json=body)

    def list(
        self,
        *,
        org_id: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Any:
        org_id = self._org(org_id)
        return self._get(f"orgs/{org_id}/sessions", params=drop_none({"limit": limit, "offset": offset}))

    def retrieve(self, session_id: str) -> Any:
        return self._get(f"sessions/{session_id}")

    def end(self, session_id: str) -> Any:
        return self._post(f"sessions/{session_id}/end")
