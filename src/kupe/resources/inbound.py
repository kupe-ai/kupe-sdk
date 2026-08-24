from __future__ import annotations

from typing import Any

from kupe.resources._base import APIResource, drop_none


class InboundResource(APIResource):
    def create(self, **body: Any) -> Any:
        org_id, project_id = self._scope(body.get("org_id"), body.get("project_id"))
        body.setdefault("org_id", org_id)
        body.setdefault("project_id", project_id)
        return self._post("inbound", json=body)

    def list(
        self,
        *,
        org_id: str | None = None,
        project_id: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Any:
        org_id, project_id = self._scope(org_id, project_id)
        return self._get(
            f"orgs/{org_id}/projects/{project_id}/inbound",
            params=drop_none({"limit": limit, "offset": offset}),
        )

    def retrieve(self, deployment_id: str) -> Any:
        return self._get(f"inbound/{deployment_id}")

    def update(self, deployment_id: str, **body: Any) -> Any:
        return self._patch(f"inbound/{deployment_id}", json=body)

    def delete(self, deployment_id: str) -> None:
        self._delete(f"inbound/{deployment_id}")
