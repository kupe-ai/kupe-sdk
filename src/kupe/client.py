from __future__ import annotations

import os
from typing import Any

import httpx

from kupe._models import KupeObject, parse
from kupe._urls import DEFAULT_BASE_URL, origin, v1_url
from kupe.errors import APIConnectionError, APIError, AuthenticationError, JWTRequiredError, KupeError
from kupe.resources.agents import AgentsResource
from kupe.resources.analyses import AnalysesResource
from kupe.resources.billing import BillingResource
from kupe.resources.campaigns import CampaignsResource
from kupe.resources.composio import ComposioResource
from kupe.resources.databases import DatabasesResource
from kupe.resources.inbound import InboundResource
from kupe.resources.knowledge_bases import KnowledgeBasesResource
from kupe.resources.logs import LogsResource
from kupe.resources.orgs import OrgsResource
from kupe.resources.phones import PhonesResource
from kupe.resources.projects import ProjectsResource
from kupe.resources.providers import ProvidersResource
from kupe.resources.realtime import RealtimeResource
from kupe.resources.recipient_lists import RecipientListsResource
from kupe.resources.sessions import SessionsResource
from kupe.resources.tools import ToolsResource
from kupe.resources.usage import UsageResource
from kupe.resources.voices import VoicesResource

__version__ = "0.3.1"


def _looks_like_jwt(token: str) -> bool:
    return (not token.startswith("sk-")) and token.count(".") == 2


class Kupe:
    """Synchronous client for the Kupe HTTP API and realtime WebSocket.

    Parameters
    ----------
    api_key:
        ``sk-kupe-...`` or a Supabase user JWT. Defaults to ``KUPE_API_KEY``.
    base_url:
        API origin, default ``https://x.kupe.in``. ``/v1`` is always appended;
        passing ``https://x.kupe.in/v1`` is fine and will not double-prefix.
    org_id / project_id:
        Optional. When omitted, filled from ``GET /v1/me``.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        org_id: str | None = None,
        project_id: str | None = None,
        timeout: float = 60.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        key = api_key if api_key is not None else os.environ.get("KUPE_API_KEY")
        if not key:
            raise AuthenticationError("No API key provided. Pass api_key= or set KUPE_API_KEY.")
        self.api_key = key
        env_base = os.environ.get("KUPE_BASE_URL")
        self.base_url = origin(base_url if base_url is not None else (env_base or DEFAULT_BASE_URL))
        self._org_id = org_id
        self._project_id = project_id
        self._owns_http = http_client is None
        self._http = http_client or httpx.Client(
            timeout=timeout,
            headers={"User-Agent": f"kupe-python/{__version__}"},
        )

        self.agents = AgentsResource(self)
        self.realtime = RealtimeResource(self)
        self.sessions = SessionsResource(self)
        self.inbound = InboundResource(self)
        self.campaigns = CampaignsResource(self)
        self.recipient_lists = RecipientListsResource(self)
        self.tools = ToolsResource(self)
        self.composio = ComposioResource(self)
        self.analyses = AnalysesResource(self)
        self.databases = DatabasesResource(self)
        self.knowledge_bases = KnowledgeBasesResource(self)
        self.phones = PhonesResource(self)
        self.voices = VoicesResource(self)
        self.providers = ProvidersResource(self)
        self.logs = LogsResource(self)
        self.billing = BillingResource(self)
        self.usage = UsageResource(self)
        self.orgs = OrgsResource(self)
        self.projects = ProjectsResource(self)

    @property
    def org_id(self) -> str | None:
        if self._org_id is None:
            self._ensure_scope()
        return self._org_id

    @property
    def project_id(self) -> str | None:
        if self._project_id is None:
            self._ensure_scope()
        return self._project_id

    def me(self) -> KupeObject:
        return self._request("GET", "me")

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> Kupe:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _uses_jwt(self) -> bool:
        return _looks_like_jwt(self.api_key)

    def _require_jwt(self, action: str) -> None:
        if not self._uses_jwt():
            raise JWTRequiredError(
                f"{action} requires a user JWT. API keys cannot own a voice — "
                "sign in and pass a Supabase access token as api_key=."
            )

    def _ensure_scope(self) -> None:
        if self._org_id and self._project_id:
            return
        try:
            me = self.me()
            data = me.to_dict() if isinstance(me, KupeObject) else dict(me)
            if not self._org_id:
                self._org_id = data.get("org_id") or None
            if not self._project_id:
                self._project_id = data.get("project_id") or None
        except APIError as exc:
            # Older deployments may not expose GET /v1/me yet. Fall back to the
            # feature-flags + projects endpoints that API keys can already call.
            if getattr(exc, "status_code", None) not in (404, 405):
                raise
        if self._org_id and self._project_id:
            return
        flags = self._request("GET", "feature-flags")
        flag_data = flags.to_dict() if isinstance(flags, KupeObject) else dict(flags)
        if not self._org_id:
            self._org_id = flag_data.get("org_id") or None
        if not self._org_id:
            return
        if not self._project_id:
            projects = self._request(
                "GET",
                f"orgs/{self._org_id}/projects",
                params={"limit": 1, "offset": 0},
            )
            proj = projects.to_dict() if isinstance(projects, KupeObject) else dict(projects)
            items = proj.get("items") or []
            if items:
                first = items[0]
                first_data = first.to_dict() if isinstance(first, KupeObject) else dict(first)
                self._project_id = first_data.get("id") or None

    def _org(self, org_id: str | None = None) -> str:
        if org_id:
            return org_id
        self._ensure_scope()
        if not self._org_id:
            raise KupeError(
                "org_id is required. Pass org_id= to Kupe() or ensure GET /v1/me returns org_id."
            )
        return self._org_id

    def _scope(
        self,
        org_id: str | None = None,
        project_id: str | None = None,
    ) -> tuple[str, str]:
        if not org_id or not project_id:
            self._ensure_scope()
        resolved_org = org_id or self._org_id
        resolved_project = project_id or self._project_id
        if not resolved_org or not resolved_project:
            raise KupeError(
                "org_id and project_id are required. Pass them to Kupe() or "
                "ensure GET /v1/me returns both."
            )
        return resolved_org, resolved_project

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
        files: Any = None,
        data: Any = None,
        raw: bool = False,
    ) -> Any:
        url = v1_url(self.base_url, path)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": f"kupe-python/{__version__}",
        }
        if not raw:
            headers["Accept"] = "application/json"

        request_kwargs: dict[str, Any] = {
            "headers": headers,
            "params": {k: v for k, v in (params or {}).items() if v is not None} or None,
        }
        if files is not None:
            request_kwargs["files"] = files
            if data is not None:
                request_kwargs["data"] = data
        elif data is not None:
            request_kwargs["data"] = data
        elif json is not None:
            request_kwargs["json"] = json

        try:
            response = self._http.request(method, url, **request_kwargs)
        except httpx.RequestError as exc:
            raise APIConnectionError(f"Failed to reach {url}: {exc}") from exc

        if response.status_code >= 400:
            try:
                body: Any = response.json()
                detail = body.get("detail", body) if isinstance(body, dict) else body
            except Exception:
                body = response.text
                detail = body
            raise APIError(
                f"HTTP {response.status_code} for {method} {url}: {detail}",
                status_code=response.status_code,
                body=body,
                path=url,
            )

        if raw:
            return response.content
        if response.status_code == 204 or not response.content:
            return None
        try:
            payload = response.json()
        except Exception:
            return response.text
        return parse(payload)
