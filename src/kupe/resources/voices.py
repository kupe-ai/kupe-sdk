from __future__ import annotations

from typing import Any, BinaryIO

from kupe.resources._base import APIResource, drop_none


class VoicesResource(APIResource):
    def list(self, *, provider: str | None = None, provider_id: str | None = None) -> Any:
        return self._get("voices", params=drop_none({"provider": provider, "provider_id": provider_id}))

    def list_mine(self, **kwargs: Any) -> Any:
        self._client._require_jwt("Voice listing of private clones")
        return self.list(**kwargs)

    def clone(
        self,
        *,
        name: str,
        sample: BinaryIO | tuple[str, bytes] | bytes | Any,
        is_public: bool = False,
        filename: str = "sample.wav",
        content_type: str = "application/octet-stream",
    ) -> Any:
        self._client._require_jwt("Voice clone")
        file_tuple = _as_file(sample, filename, content_type)
        return self._post(
            "voices/clone",
            data={"name": name, "is_public": str(is_public).lower()},
            files={"sample": file_tuple},
        )

    def update(
        self,
        voice_id: str,
        *,
        name: str | None = None,
        is_public: bool | None = None,
    ) -> Any:
        self._client._require_jwt("Voice update")
        data: dict[str, Any] = {}
        if name is not None:
            data["name"] = name
        if is_public is not None:
            data["is_public"] = str(is_public).lower()
        return self._patch(f"voices/{voice_id}", data=data)

    def delete(self, voice_id: str, *, fallback_voice_id: str | None = None) -> None:
        self._client._require_jwt("Voice delete")
        self._delete(f"voices/{voice_id}", params=drop_none({"fallback_voice_id": fallback_voice_id}))

    def usage(self, voice_id: str) -> Any:
        self._client._require_jwt("Voice usage")
        return self._get(f"voices/{voice_id}/usage")

    def preview(self, voice_id: str) -> bytes:
        return self._get(f"voices/{voice_id}/preview", raw=True)

    def speak(self, voice_id: str, *, text: str, org_id: str | None = None, **extra: Any) -> bytes:
        self._client._require_jwt("Voice speak")
        body = {"text": text, "org_id": self._org(org_id), **extra}
        return self._post(f"voices/{voice_id}/speak", json=body, raw=True)


def _as_file(
    sample: BinaryIO | tuple[str, bytes] | bytes | Any,
    filename: str,
    content_type: str,
) -> Any:
    if isinstance(sample, tuple):
        return sample
    if isinstance(sample, (bytes, bytearray)):
        return (filename, bytes(sample), content_type)
    return (filename, sample, content_type)
