from kupe.client import Kupe
from kupe.errors import APIError, AuthenticationError, JWTRequiredError, KupeError
from kupe.realtime import RealtimeConnection
from kupe.thinkspark import Decision, ThinkSpark

__all__ = [
    "Kupe",
    "KupeError",
    "APIError",
    "AuthenticationError",
    "JWTRequiredError",
    "RealtimeConnection",
    "ThinkSpark",
    "Decision",
]
__version__ = "0.1.6"
