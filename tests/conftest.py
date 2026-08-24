from __future__ import annotations

from typing import Any, Callable

import httpx

from kupe import Kupe


def mock_client(
    handler: Callable[[httpx.Request], httpx.Response],
    **kwargs: Any,
) -> Kupe:
    transport = httpx.MockTransport(handler)
    http = httpx.Client(transport=transport)
    kwargs.setdefault("api_key", "sk-kupe-test")
    kwargs.setdefault("org_id", "org_1")
    kwargs.setdefault("project_id", "proj_1")
    return Kupe(http_client=http, **kwargs)
