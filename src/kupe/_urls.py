"""URL helpers. Paths always join as ``{origin}/v1/...``.

The OpenAI SDK treats a leading-slash path as host-absolute, so
``OpenAI(base_url="https://x.kupe.in/v1").post("/realtime/sessions")`` hits
``https://x.kupe.in/realtime/sessions`` (no ``/v1``). This package never
does that: every HTTP call is built with :func:`v1_url`.
"""

from __future__ import annotations

DEFAULT_BASE_URL = "https://x.kupe.in"


def origin(base_url: str | None) -> str:
    """Host origin with no trailing slash and no ``/v1`` suffix.

    Callers may pass ``https://x.kupe.in`` or ``https://x.kupe.in/v1``;
    both resolve to the same origin so we never double-prefix ``/v1``.
    """
    url = (base_url or DEFAULT_BASE_URL).strip().rstrip("/")
    if url.endswith("/v1"):
        url = url[: -len("/v1")].rstrip("/")
    return url


def v1_url(base_url: str | None, path: str) -> str:
    """Return ``{origin}/v1/{path}``. Leading slashes and a ``v1/`` prefix on
    *path* are stripped so a caller cannot accidentally drop ``/v1``.
    """
    path = (path or "").lstrip("/")
    if path.startswith("v1/"):
        path = path[3:]
    path = path.lstrip("/")
    return f"{origin(base_url)}/v1/{path}"
