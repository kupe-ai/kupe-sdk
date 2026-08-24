from __future__ import annotations

from typing import Any


class KupeError(Exception):
    """Base error for the Kupe SDK."""


class AuthenticationError(KupeError):
    """Missing or invalid credentials."""


class JWTRequiredError(AuthenticationError):
    """This method requires a user JWT; API keys are not accepted.

    Voice clone / patch / delete (and related ownership endpoints) are
    JWT-only on the backend — API keys cannot own a voice.
    """


class APIConnectionError(KupeError):
    """Network failure talking to the Kupe API."""


class APIError(KupeError):
    """Non-success HTTP response from the Kupe API."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        body: Any = None,
        path: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body
        self.path = path
