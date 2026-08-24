from __future__ import annotations

from typing import Any

from kupe.resources._base import APIResource, drop_none


class AnalysisToolsResource(APIResource):
    def list(self, analysis_id: str, *, limit: int | None = None, offset: int | None = None) -> Any:
        return self._get(
            f"post-call-analyses/{analysis_id}/tools",
            params=drop_none({"limit": limit, "offset": offset}),
        )

    def attach(self, analysis_id: str, **body: Any) -> Any:
        return self._post(f"post-call-analyses/{analysis_id}/tools", json=body)

    def detach(self, analysis_id: str, tool_id: str) -> None:
        self._delete(f"post-call-analyses/{analysis_id}/tools/{tool_id}")


class AnalysesResource(APIResource):
    """Org-level post-call analysis configs plus per-session results."""

    def __init__(self, client: Any) -> None:
        super().__init__(client)
        self.tools = AnalysisToolsResource(client)

    def create(self, **body: Any) -> Any:
        org_id = self._org(body.pop("org_id", None))
        return self._post(f"orgs/{org_id}/post-call-analyses", json=body)

    def list(self, *, org_id: str | None = None, limit: int | None = None, offset: int | None = None) -> Any:
        org_id = self._org(org_id)
        return self._get(
            f"orgs/{org_id}/post-call-analyses",
            params=drop_none({"limit": limit, "offset": offset}),
        )

    def retrieve(self, analysis_id: str) -> Any:
        return self._get(f"post-call-analyses/{analysis_id}")

    def update(self, analysis_id: str, **body: Any) -> Any:
        return self._patch(f"post-call-analyses/{analysis_id}", json=body)

    def archive(self, analysis_id: str) -> Any:
        return self._post(f"post-call-analyses/{analysis_id}/archive")

    def session_results(
        self,
        session_id: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Any:
        return self._get(
            f"sessions/{session_id}/analysis",
            params=drop_none({"limit": limit, "offset": offset}),
        )
