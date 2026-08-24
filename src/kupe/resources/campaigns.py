from __future__ import annotations

from typing import Any, BinaryIO

from kupe.resources._base import APIResource, drop_none


class CampaignContactsResource(APIResource):
    def list(
        self,
        campaign_id: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        cursor: str | None = None,
        status: str | None = None,
        search: str | None = None,
    ) -> Any:
        return self._get(
            f"batches/{campaign_id}/contacts",
            params=drop_none(
                {
                    "limit": limit,
                    "offset": offset,
                    "cursor": cursor,
                    "status": status,
                    "search": search,
                }
            ),
        )

    def add(self, campaign_id: str, *, contacts: list[dict[str, Any]] | None = None, **body: Any) -> Any:
        payload = body
        if contacts is not None:
            payload = {"contacts": contacts, **body}
        return self._post(f"batches/{campaign_id}/contacts:bulk", json=payload)

    def add_csv(self, campaign_id: str, file: BinaryIO | tuple[str, bytes] | Any) -> Any:
        return self._post(f"batches/{campaign_id}/contacts", files={"file": file})

    def delete(self, campaign_id: str, **body: Any) -> Any:
        return self._delete(f"batches/{campaign_id}/contacts:bulk", json=body)

    def attach_list(self, campaign_id: str, **body: Any) -> Any:
        return self._post(f"batches/{campaign_id}/contacts:from-list", json=body)


class CampaignsResource(APIResource):
    """Outbound batches/campaigns (backend path: ``/v1/batches``)."""

    def __init__(self, client: Any) -> None:
        super().__init__(client)
        self.contacts = CampaignContactsResource(client)

    def create(self, **body: Any) -> Any:
        org_id, project_id = self._scope(body.get("org_id"), body.get("project_id"))
        body.setdefault("org_id", org_id)
        body.setdefault("project_id", project_id)
        return self._post("batches", json=body)

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
            f"orgs/{org_id}/projects/{project_id}/batches",
            params=drop_none({"limit": limit, "offset": offset}),
        )

    def retrieve(self, campaign_id: str) -> Any:
        return self._get(f"batches/{campaign_id}")

    def stats(self, campaign_id: str) -> Any:
        return self._get(f"batches/{campaign_id}/stats")

    def call_analytics(self, campaign_id: str) -> Any:
        return self._get(f"batches/{campaign_id}/call-analytics")

    def analytics(
        self,
        *,
        org_id: str | None = None,
        project_id: str | None = None,
        campaign_id: str | None = None,
        search: str | None = None,
    ) -> Any:
        org_id, project_id = self._scope(org_id, project_id)
        return self._get(
            f"orgs/{org_id}/projects/{project_id}/batches/analytics",
            params=drop_none({"batch_id": campaign_id, "search": search}),
        )

    def update_schedule(self, campaign_id: str, **body: Any) -> Any:
        return self._patch(f"batches/{campaign_id}/schedule", json=body)

    def start(self, campaign_id: str) -> Any:
        return self._post(f"batches/{campaign_id}/start")

    def pause(self, campaign_id: str) -> Any:
        return self._post(f"batches/{campaign_id}/pause")

    def resume(self, campaign_id: str) -> Any:
        return self._post(f"batches/{campaign_id}/resume")

    def cancel(self, campaign_id: str) -> Any:
        return self._post(f"batches/{campaign_id}/cancel")

    def hide(self, campaign_id: str) -> None:
        self._post(f"batches/{campaign_id}/hide")

    def unhide_all(self, *, org_id: str | None = None, project_id: str | None = None) -> Any:
        org_id, project_id = self._scope(org_id, project_id)
        return self._post(f"orgs/{org_id}/projects/{project_id}/batches:unhide")

    def delete(self, campaign_id: str) -> None:
        self._delete(f"batches/{campaign_id}")
