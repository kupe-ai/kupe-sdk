from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kupe.client import Kupe


def drop_none(mapping: dict[str, Any] | None) -> dict[str, Any] | None:
    if mapping is None:
        return None
    return {key: value for key, value in mapping.items() if value is not None}


class APIResource:
    def __init__(self, client: Kupe) -> None:
        self._client = client

    def _get(self, path: str, **kwargs: Any) -> Any:
        return self._client._request("GET", path, **kwargs)

    def _post(self, path: str, **kwargs: Any) -> Any:
        return self._client._request("POST", path, **kwargs)

    def _patch(self, path: str, **kwargs: Any) -> Any:
        return self._client._request("PATCH", path, **kwargs)

    def _delete(self, path: str, **kwargs: Any) -> Any:
        return self._client._request("DELETE", path, **kwargs)

    def _scope(
        self,
        org_id: str | None = None,
        project_id: str | None = None,
    ) -> tuple[str, str]:
        return self._client._scope(org_id=org_id, project_id=project_id)

    def _org(self, org_id: str | None = None) -> str:
        return self._client._org(org_id)
