from __future__ import annotations

import httpx
import pytest

from kupe import APIError, AuthenticationError, Kupe, KupeError
from tests.conftest import mock_client


def test_missing_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KUPE_API_KEY", raising=False)
    with pytest.raises(AuthenticationError, match="KUPE_API_KEY"):
        Kupe(api_key="")


def test_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KUPE_API_KEY", "sk-kupe-from-env")
    monkeypatch.setenv("KUPE_BASE_URL", "https://staging.kupe.in/v1")
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"ok": True})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = Kupe(http_client=http, org_id="o", project_id="p")
    assert client.api_key == "sk-kupe-from-env"
    assert client.base_url == "https://staging.kupe.in"
    client.providers.list()
    assert str(captured[0].url) == "https://staging.kupe.in/v1/providers"
    client.close()


def test_base_url_with_v1_still_keeps_v1() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"items": []})

    client = mock_client(handler, base_url="https://x.kupe.in/v1")
    client.agents.list()
    assert str(captured[0].url.path) == "/v1/orgs/org_1/projects/proj_1/agents"
    assert str(captured[0].url).startswith("https://x.kupe.in/v1/")
    client.close()


def test_autofill_org_project_from_me() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        if request.url.path == "/v1/me":
            return httpx.Response(
                200,
                json={"org_id": "org_me", "project_id": "proj_me", "auth": "api_key"},
            )
        return httpx.Response(200, json={"items": [], "total": 0})

    client = mock_client(handler, org_id=None, project_id=None)
    page = client.agents.list()
    assert [r.url.path for r in captured] == [
        "/v1/me",
        "/v1/orgs/org_me/projects/proj_me/agents",
    ]
    assert page.items == []
    client.close()


def test_http_error_raises_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "not found"})

    client = mock_client(handler)
    with pytest.raises(APIError) as exc:
        client.agents.retrieve("agt_missing")
    assert exc.value.status_code == 404
    assert "not found" in str(exc.value)
    assert exc.value.path and "/v1/agents/agt_missing" in exc.value.path
    client.close()


def test_me_missing_ids_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"auth": "jwt"})

    client = mock_client(handler, org_id=None, project_id=None)
    with pytest.raises(KupeError, match="org_id and project_id"):
        client.agents.list()
    client.close()
