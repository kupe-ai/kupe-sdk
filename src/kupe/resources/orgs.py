from __future__ import annotations

from typing import Any

from kupe.resources._base import APIResource, drop_none


class OrgsResource(APIResource):
    def create(self, **body: Any) -> Any:
        return self._post("orgs", json=body)

    def list(self, *, limit: int | None = None, offset: int | None = None) -> Any:
        return self._get("orgs", params=drop_none({"limit": limit, "offset": offset}))

    def retrieve(self, org_id: str | None = None) -> Any:
        org_id = self._org(org_id)
        return self._get(f"orgs/{org_id}")

    def update(self, org_id: str | None = None, **body: Any) -> Any:
        org_id = self._org(org_id)
        return self._patch(f"orgs/{org_id}", json=body)
