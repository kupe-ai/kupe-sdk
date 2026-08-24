from kupe._urls import origin, v1_url


def test_origin_strips_trailing_slash_and_v1() -> None:
    assert origin("https://x.kupe.in") == "https://x.kupe.in"
    assert origin("https://x.kupe.in/") == "https://x.kupe.in"
    assert origin("https://x.kupe.in/v1") == "https://x.kupe.in"
    assert origin("https://x.kupe.in/v1/") == "https://x.kupe.in"


def test_v1_url_never_drops_v1() -> None:
    assert v1_url("https://x.kupe.in", "realtime/sessions") == "https://x.kupe.in/v1/realtime/sessions"
    assert v1_url("https://x.kupe.in/v1", "/realtime/sessions") == "https://x.kupe.in/v1/realtime/sessions"
    assert v1_url("https://x.kupe.in/v1", "/v1/realtime/sessions") == "https://x.kupe.in/v1/realtime/sessions"
    assert v1_url("https://x.kupe.in", "v1/agents/agt_1") == "https://x.kupe.in/v1/agents/agt_1"
