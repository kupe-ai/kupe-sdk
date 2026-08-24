from __future__ import annotations

from typing import Any

from kupe.resources._base import APIResource, drop_none


class DatabasesResource(APIResource):
    def create(self, **body: Any) -> Any:
        org_id, project_id = self._scope(body.pop("org_id", None), body.pop("project_id", None))
        return self._post(f"orgs/{org_id}/projects/{project_id}/databases", json=body)

    def list(
        self,
        *,
        org_id: str | None = None,
        project_id: str | None = None,
        search: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Any:
        org_id, project_id = self._scope(org_id, project_id)
        return self._get(
            f"orgs/{org_id}/projects/{project_id}/databases",
            params=drop_none({"search": search, "limit": limit, "offset": offset}),
        )

    def retrieve(self, database_id: str) -> Any:
        return self._get(f"databases/{database_id}")

    def update(self, database_id: str, **body: Any) -> Any:
        return self._patch(f"databases/{database_id}", json=body)

    def archive(self, database_id: str) -> Any:
        return self._post(f"databases/{database_id}/archive")

    def list_agents(self, database_id: str) -> Any:
        return self._get(f"databases/{database_id}/agents")

    def attach_agent(self, database_id: str, **body: Any) -> Any:
        return self._post(f"databases/{database_id}/agents", json=body)

    def detach_agent(self, database_id: str, agent_id: str) -> None:
        self._delete(f"databases/{database_id}/agents/{agent_id}")

    def rows(
        self,
        database_id: str,
        *,
        cursor: str | None = None,
        limit: int | None = None,
        q: str | None = None,
    ) -> Any:
        return self._get(
            f"databases/{database_id}/rows",
            params=drop_none({"cursor": cursor, "limit": limit, "q": q}),
        )

    def export(
        self,
        database_id: str,
        *,
        format: str = "csv",
        q: str | None = None,
    ) -> bytes:
        return self._get(
            f"databases/{database_id}/export",
            params=drop_none({"format": format, "q": q}),
            raw=True,
        )
