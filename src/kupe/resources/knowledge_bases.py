from __future__ import annotations

from typing import Any, BinaryIO

from kupe.resources._base import APIResource, drop_none


class KnowledgeBaseFilesResource(APIResource):
    def list(
        self,
        kb_id: str,
        *,
        org_id: str | None = None,
        project_id: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Any:
        org_id, project_id = self._scope(org_id, project_id)
        return self._get(
            f"orgs/{org_id}/projects/{project_id}/knowledge-bases/{kb_id}/files",
            params=drop_none({"limit": limit, "offset": offset}),
        )

    def upload(
        self,
        kb_id: str,
        file: BinaryIO | tuple[str, bytes] | Any,
        *,
        org_id: str | None = None,
        project_id: str | None = None,
    ) -> Any:
        org_id, project_id = self._scope(org_id, project_id)
        return self._post(
            f"orgs/{org_id}/projects/{project_id}/knowledge-bases/{kb_id}/files",
            files={"file": file},
        )

    def delete(
        self,
        kb_id: str,
        file_id: str,
        *,
        org_id: str | None = None,
        project_id: str | None = None,
    ) -> Any:
        org_id, project_id = self._scope(org_id, project_id)
        return self._delete(f"orgs/{org_id}/projects/{project_id}/knowledge-bases/{kb_id}/files/{file_id}")


class AudioAssetsResource(APIResource):
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
            f"orgs/{org_id}/projects/{project_id}/audio-assets",
            params=drop_none({"limit": limit, "offset": offset}),
        )

    def upload(
        self,
        *,
        name: str,
        file: BinaryIO | tuple[str, bytes] | Any,
        org_id: str | None = None,
        project_id: str | None = None,
    ) -> Any:
        org_id, project_id = self._scope(org_id, project_id)
        return self._post(
            f"orgs/{org_id}/projects/{project_id}/audio-assets",
            data={"name": name},
            files={"file": file},
        )

    def archive(self, asset_id: str) -> Any:
        return self._post(f"audio-assets/{asset_id}/archive")


class KnowledgeBasesResource(APIResource):
    def __init__(self, client: Any) -> None:
        super().__init__(client)
        self.files = KnowledgeBaseFilesResource(client)
        self.audio_assets = AudioAssetsResource(client)

    def create(self, **body: Any) -> Any:
        org_id, project_id = self._scope(body.pop("org_id", None), body.pop("project_id", None))
        return self._post(f"orgs/{org_id}/projects/{project_id}/knowledge-bases", json=body)

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
            f"orgs/{org_id}/projects/{project_id}/knowledge-bases",
            params=drop_none({"search": search, "limit": limit, "offset": offset}),
        )

    def retrieve(self, kb_id: str, *, org_id: str | None = None, project_id: str | None = None) -> Any:
        org_id, project_id = self._scope(org_id, project_id)
        return self._get(f"orgs/{org_id}/projects/{project_id}/knowledge-bases/{kb_id}")

    def update(self, kb_id: str, *, org_id: str | None = None, project_id: str | None = None, **body: Any) -> Any:
        org_id, project_id = self._scope(org_id, project_id)
        return self._patch(f"orgs/{org_id}/projects/{project_id}/knowledge-bases/{kb_id}", json=body)

    def delete(self, kb_id: str, *, org_id: str | None = None, project_id: str | None = None) -> Any:
        org_id, project_id = self._scope(org_id, project_id)
        return self._delete(f"orgs/{org_id}/projects/{project_id}/knowledge-bases/{kb_id}")

    def search(self, kb_id: str, *, query: str, top_k: int | None = None, org_id: str | None = None, project_id: str | None = None) -> Any:
        org_id, project_id = self._scope(org_id, project_id)
        body: dict[str, Any] = {"query": query}
        if top_k is not None:
            body["top_k"] = top_k
        return self._post(f"orgs/{org_id}/projects/{project_id}/knowledge-bases/{kb_id}/search", json=body)
