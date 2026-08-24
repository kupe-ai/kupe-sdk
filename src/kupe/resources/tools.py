from __future__ import annotations

from typing import Any

from kupe.resources._base import APIResource, drop_none


class ToolsResource(APIResource):
    def create(self, **body: Any) -> Any:
        org_id = self._org(body.pop("org_id", None))
        return self._post(f"orgs/{org_id}/tools", json=body)

    def list(self, *, org_id: str | None = None, limit: int | None = None, offset: int | None = None) -> Any:
        org_id = self._org(org_id)
        return self._get(f"orgs/{org_id}/tools", params=drop_none({"limit": limit, "offset": offset}))

    def retrieve(self, tool_id: str) -> Any:
        return self._get(f"tools/{tool_id}")

    def update(self, tool_id: str, **body: Any) -> Any:
        return self._patch(f"tools/{tool_id}", json=body)

    def archive(self, tool_id: str) -> Any:
        return self._post(f"tools/{tool_id}/archive")
