from __future__ import annotations

from typing import Any, BinaryIO

from kupe.resources._base import APIResource, drop_none


class RecipientListMembersResource(APIResource):
    def list(self, list_id: str, *, limit: int | None = None, cursor: str | None = None) -> Any:
        return self._get(
            f"recipient-lists/{list_id}/members",
            params=drop_none({"limit": limit, "cursor": cursor}),
        )

    def add_bulk(self, list_id: str, **body: Any) -> Any:
        return self._post(f"recipient-lists/{list_id}/members:bulk", json=body)

    def add_csv(self, list_id: str, file: BinaryIO | tuple[str, bytes] | Any) -> Any:
        return self._post(f"recipient-lists/{list_id}/members", files={"file": file})

    def update(self, list_id: str, member_id: str, **body: Any) -> Any:
        return self._patch(f"recipient-lists/{list_id}/members/{member_id}", json=body)

    def delete(self, list_id: str, member_id: str) -> None:
        self._delete(f"recipient-lists/{list_id}/members/{member_id}")


class RecipientListsResource(APIResource):
    def __init__(self, client: Any) -> None:
        super().__init__(client)
        self.members = RecipientListMembersResource(client)

    def create(self, **body: Any) -> Any:
        org_id, project_id = self._scope(body.get("org_id"), body.get("project_id"))
        body.setdefault("org_id", org_id)
        body.setdefault("project_id", project_id)
        return self._post("recipient-lists", json=body)

    def list(
        self,
        *,
        org_id: str | None = None,
        project_id: str | None = None,
        name: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Any:
        org_id, project_id = self._scope(org_id, project_id)
        return self._get(
            f"orgs/{org_id}/projects/{project_id}/recipient-lists",
            params=drop_none({"name": name, "limit": limit, "offset": offset}),
        )

    def retrieve(self, list_id: str) -> Any:
        return self._get(f"recipient-lists/{list_id}")

    def update(self, list_id: str, **body: Any) -> Any:
        return self._patch(f"recipient-lists/{list_id}", json=body)

    def delete(self, list_id: str) -> None:
        self._delete(f"recipient-lists/{list_id}")

    def attach_to_campaign(self, campaign_id: str, **body: Any) -> Any:
        return self._post(f"batches/{campaign_id}/contacts:from-list", json=body)
