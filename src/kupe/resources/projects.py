from __future__ import annotations

from typing import Any

from kupe.resources._base import APIResource, drop_none


class ProjectsResource(APIResource):
    def create(self, **body: Any) -> Any:
        org_id = self._org(body.pop("org_id", None))
        return self._post(f"orgs/{org_id}/projects", json=body)

    def list(self, *, org_id: str | None = None, limit: int | None = None, offset: int | None = None) -> Any:
        org_id = self._org(org_id)
        return self._get(f"orgs/{org_id}/projects", params=drop_none({"limit": limit, "offset": offset}))

    def archive(self, project_id: str) -> Any:
        return self._post(f"projects/{project_id}/archive")
