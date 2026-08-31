from __future__ import annotations

import json

import httpx

from tests.conftest import mock_client


def test_agents_crud_paths() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        if request.method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(200, json={"id": "agt_1", "name": "Bot"})

    client = mock_client(handler)
    client.agents.create(name="Bot", system_prompt="Hi")
    client.agents.retrieve("agt_1")
    client.agents.update("agt_1", greeting="hello")
    client.agents.commit("agt_1")
    client.agents.archive("agt_1")
    client.agents.versions.list("agt_1")
    client.agents.revert("agt_1", 2)
    client.agents.tools.attach("agt_1", tool_id="tool_1")
    client.agents.tools.detach("agt_1", "tool_1")
    client.agents.analyses.list("agt_1")
    client.agents.memories.list("agt_1", contact="+1555")
    client.agents.tests.create("agt_1", name="t1")
    paths = [r.url.path for r in captured]
    assert paths[0] == "/v1/orgs/org_1/projects/proj_1/agents"
    assert paths[1] == "/v1/agents/agt_1"
    assert "/v1/agents/agt_1/commit" in paths
    assert "/v1/agents/agt_1/archive" in paths
    assert "/v1/agents/agt_1/versions" in paths
    assert "/v1/agents/agt_1/revert/2" in paths
    assert "/v1/agents/agt_1/tools" in paths
    assert "/v1/agents/agt_1/post-call-analyses" in paths
    assert "/v1/agents/agt_1/memories" in paths
    client.close()


def test_sessions_inbound_campaigns_lists() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        if request.method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(200, json={"id": "x"})

    client = mock_client(handler)
    client.sessions.create(agent_id="agt_1", channel="web")
    client.sessions.list()
    client.sessions.end("sess_1")
    client.inbound.create(agent_id="agt_1", phone_number="+1")
    client.inbound.list()
    client.campaigns.create(agent_id="agt_1", telephony_account_id="tel_1", name="c")
    client.campaigns.start("bat_1")
    client.campaigns.pause("bat_1")
    client.recipient_lists.create(name="vip")
    client.tools.create(name="webhook", kind="webhook")
    client.composio.list_toolkits()
    client.analyses.create(name="csat")
    client.databases.create(name="leads")
    client.knowledge_bases.list()
    client.phones.search(country_iso="IN")
    client.phones.buy(number="+911")
    client.phones.delete("tel_1")
    client.providers.list()
    client.logs.transcript("sess_1")
    client.logs.recording("sess_1")
    client.logs.tool_call_events()
    client.orgs.retrieve()
    client.projects.list()
    paths = [r.url.path for r in captured]
    assert "/v1/sessions" in paths
    assert "/v1/orgs/org_1/sessions" in paths
    assert "/v1/inbound" in paths
    assert "/v1/batches" in paths
    assert "/v1/batches/bat_1/start" in paths
    assert "/v1/recipient-lists" in paths
    assert "/v1/orgs/org_1/tools" in paths
    assert "/v1/orgs/org_1/composio/toolkits" in paths
    assert "/v1/orgs/org_1/post-call-analyses" in paths
    assert "/v1/orgs/org_1/projects/proj_1/databases" in paths
    assert "/v1/orgs/org_1/projects/proj_1/knowledge-bases" in paths
    assert "/v1/orgs/org_1/plivo/numbers/search" in paths
    assert "/v1/orgs/org_1/plivo/numbers/purchase" in paths
    assert "/v1/telephony-accounts/tel_1" in paths
    assert "/v1/providers" in paths
    assert "/v1/sessions/sess_1/transcript" in paths
    assert "/v1/sessions/sess_1/recording" in paths
    assert "/v1/orgs/org_1/tool-call-events" in paths
    assert "/v1/orgs/org_1" in paths
    assert "/v1/orgs/org_1/projects" in paths
    client.close()


def test_phones_ucc_paths() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"items": [], "total": 0, "actionable_count": 0})

    client = mock_client(handler)
    client.phones.ucc_list(status="pending", from_number="+9111")
    client.phones.ucc_summary()
    client.phones.ucc_retrieve("PUCC-2026-1")
    client.phones.ucc_submit_proof("PUCC-2026-1", file=("proof.pdf", b"%PDF", "application/pdf"))
    client.phones.ucc_sync()
    paths = [r.url.path for r in captured]
    assert paths == [
        "/v1/orgs/org_1/plivo/ucc",
        "/v1/orgs/org_1/plivo/ucc/summary",
        "/v1/orgs/org_1/plivo/ucc/PUCC-2026-1",
        "/v1/orgs/org_1/plivo/ucc/PUCC-2026-1/proof",
        "/v1/orgs/org_1/plivo/ucc/sync",
    ]
    assert captured[0].url.params.get("status") == "pending"
    assert captured[0].url.params.get("from_number") == "+9111"
    assert captured[3].method == "POST"
    assert "multipart/form-data" in captured[3].headers["content-type"]
    assert captured[4].method == "POST"
    client.close()


def test_usage_only_cost_summary_and_daily() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"items": []})

    client = mock_client(handler)
    client.usage.cost_summary(start_date="2026-01-01")
    client.usage.daily(start_date="2026-01-01", end_date="2026-01-31")
    paths = [r.url.path for r in captured]
    assert paths == [
        "/v1/orgs/org_1/usage/cost-summary",
        "/v1/orgs/org_1/usage/daily",
    ]
    assert not hasattr(client.usage, "summary")
    assert not hasattr(client.usage, "sessions")
    client.close()


def test_billing_wallet_and_invoices_not_checkout() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        if request.url.path.endswith("/pdf"):
            return httpx.Response(200, content=b"%PDF")
        return httpx.Response(200, json={"balance_cents": 1})

    client = mock_client(handler)
    client.billing.wallet()
    client.billing.invoices()
    pdf = client.billing.invoice_pdf("inv_1")
    assert pdf == b"%PDF"
    paths = [r.url.path for r in captured]
    assert paths == [
        "/v1/orgs/org_1/billing/wallet",
        "/v1/orgs/org_1/billing/invoices",
        "/v1/orgs/org_1/billing/invoices/inv_1/pdf",
    ]
    for forbidden in ("topup", "checkout", "subscribe"):
        assert not any(forbidden in p for p in paths)
    assert not hasattr(client.billing, "topup")
    assert not hasattr(client.billing, "checkout")
    client.close()


def test_campaign_create_json_includes_scope() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"id": "bat_1"})

    client = mock_client(handler)
    client.campaigns.create(agent_id="agt_1", telephony_account_id="tel_1", name="out")
    body = json.loads(captured[0].content)
    assert body["org_id"] == "org_1"
    assert body["project_id"] == "proj_1"
    client.close()
