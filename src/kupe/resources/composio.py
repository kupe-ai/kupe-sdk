from __future__ import annotations

from typing import Any

from kupe.resources._base import APIResource, drop_none


class ComposioResource(APIResource):
    def list_toolkits(
        self,
        *,
        org_id: str | None = None,
        category: str | None = None,
        cursor: str | None = None,
    ) -> Any:
        org_id = self._org(org_id)
        return self._get(
            f"orgs/{org_id}/composio/toolkits",
            params=drop_none({"category": category, "cursor": cursor}),
        )

    def list_toolkit_tools(
        self,
        toolkit_slug: str,
        *,
        org_id: str | None = None,
        cursor: str | None = None,
    ) -> Any:
        org_id = self._org(org_id)
        return self._get(
            f"orgs/{org_id}/composio/toolkits/{toolkit_slug}/tools",
            params=drop_none({"cursor": cursor}),
        )

    def list_connections(self, *, org_id: str | None = None) -> Any:
        org_id = self._org(org_id)
        return self._get(f"orgs/{org_id}/composio/connections")

    def connect(self, **body: Any) -> Any:
        org_id = self._org(body.pop("org_id", None))
        return self._post(f"orgs/{org_id}/composio/connections", json=body)

    def refresh(self, connection_id: str) -> Any:
        return self._post(f"composio/connections/{connection_id}/refresh")

    def disconnect(self, connection_id: str) -> None:
        self._delete(f"composio/connections/{connection_id}")

    def attach_tool(self, **body: Any) -> Any:
        org_id = self._org(body.pop("org_id", None))
        return self._post(f"orgs/{org_id}/composio/tools", json=body)
