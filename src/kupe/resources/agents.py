from __future__ import annotations

from typing import Any

from kupe.resources._base import APIResource, drop_none


class AgentToolsResource(APIResource):
    def list(self, agent_id: str, *, limit: int | None = None, offset: int | None = None) -> Any:
        return self._get(f"agents/{agent_id}/tools", params=drop_none({"limit": limit, "offset": offset}))

    def attach(self, agent_id: str, **body: Any) -> Any:
        return self._post(f"agents/{agent_id}/tools", json=body)

    def detach(self, agent_id: str, tool_id: str) -> None:
        self._delete(f"agents/{agent_id}/tools/{tool_id}")


class AgentAnalysesResource(APIResource):
    def list(self, agent_id: str, *, limit: int | None = None, offset: int | None = None) -> Any:
        return self._get(
            f"agents/{agent_id}/post-call-analyses",
            params=drop_none({"limit": limit, "offset": offset}),
        )

    def attach(self, agent_id: str, **body: Any) -> Any:
        return self._post(f"agents/{agent_id}/post-call-analyses", json=body)

    def detach(self, agent_id: str, analysis_id: str) -> None:
        self._delete(f"agents/{agent_id}/post-call-analyses/{analysis_id}")


class AgentMemoriesResource(APIResource):
    def list(
        self,
        agent_id: str,
        *,
        contact: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Any:
        return self._get(
            f"agents/{agent_id}/memories",
            params=drop_none({"contact": contact, "limit": limit, "offset": offset}),
        )

    def forget(self, agent_id: str, *, contact: str) -> Any:
        return self._delete(f"agents/{agent_id}/memories", params={"contact": contact})


class AgentTestsResource(APIResource):
    def create(self, agent_id: str, **body: Any) -> Any:
        return self._post(f"agents/{agent_id}/tests", json=body)

    def list(self, agent_id: str, *, limit: int | None = None, offset: int | None = None) -> Any:
        return self._get(f"agents/{agent_id}/tests", params=drop_none({"limit": limit, "offset": offset}))

    def update(self, agent_id: str, test_id: str, **body: Any) -> Any:
        return self._patch(f"agents/{agent_id}/tests/{test_id}", json=body)

    def delete(self, agent_id: str, test_id: str) -> None:
        self._delete(f"agents/{agent_id}/tests/{test_id}")

    def start_run(self, agent_id: str, **body: Any) -> Any:
        return self._post(f"agents/{agent_id}/test-runs", json=body)

    def list_runs(self, agent_id: str, *, limit: int | None = None, offset: int | None = None) -> Any:
        return self._get(f"agents/{agent_id}/test-runs", params=drop_none({"limit": limit, "offset": offset}))

    def retrieve_run(self, agent_id: str, run_id: str) -> Any:
        return self._get(f"agents/{agent_id}/test-runs/{run_id}")


class AgentVersionsResource(APIResource):
    def list(self, agent_id: str, *, limit: int | None = None, offset: int | None = None) -> Any:
        return self._get(f"agents/{agent_id}/versions", params=drop_none({"limit": limit, "offset": offset}))


class AgentsResource(APIResource):
    def __init__(self, client: Any) -> None:
        super().__init__(client)
        self.tools = AgentToolsResource(client)
        self.analyses = AgentAnalysesResource(client)
        self.memories = AgentMemoriesResource(client)
        self.tests = AgentTestsResource(client)
        self.versions = AgentVersionsResource(client)

    def create(
        self,
        **body: Any,
    ) -> Any:
        org_id, project_id = self._scope(body.pop("org_id", None), body.pop("project_id", None))
        return self._post(f"orgs/{org_id}/projects/{project_id}/agents", json=body)

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
            f"orgs/{org_id}/projects/{project_id}/agents",
            params=drop_none({"limit": limit, "offset": offset}),
        )

    def retrieve(self, agent_id: str) -> Any:
        return self._get(f"agents/{agent_id}")

    def update(self, agent_id: str, **body: Any) -> Any:
        return self._patch(f"agents/{agent_id}", json=body)

    def commit(self, agent_id: str, **body: Any) -> Any:
        return self._post(f"agents/{agent_id}/commit", json=body or None)

    def archive(self, agent_id: str) -> Any:
        return self._post(f"agents/{agent_id}/archive")

    def revert(self, agent_id: str, version: int) -> Any:
        return self._post(f"agents/{agent_id}/revert/{version}")

    def demo_variables(self, agent_id: str, **body: Any) -> Any:
        return self._post(f"agents/{agent_id}/demo-variables", json=body or None)

    def databases(self, agent_id: str) -> Any:
        return self._get(f"agents/{agent_id}/databases")
