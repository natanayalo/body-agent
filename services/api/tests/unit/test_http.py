import pytest

from app.tools import http


class DummyResponse:
    def __init__(self, url: str):
        self.url = url


def test_safe_request_allows_exact_domain(monkeypatch):
    captured = {}

    def fake_request(method, url, headers=None, allow_redirects=None, **kwargs):
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = headers
        captured["allow_redirects"] = allow_redirects
        captured["kwargs"] = kwargs
        return DummyResponse(url)

    monkeypatch.setattr(http.requests, "request", fake_request)

    resp = http.safe_request(
        "get",
        "https://example.com/path",
        allowlist=["example.com"],
        headers={"x": "y"},
        timeout=5,
    )

    assert isinstance(resp, DummyResponse)
    assert captured["method"] == "GET"
    assert captured["url"] == "https://example.com/path"
    assert captured["headers"] == {"x": "y"}
    assert captured["allow_redirects"] is False
    assert captured["kwargs"]["timeout"] == 5


def test_safe_request_allows_subdomain(monkeypatch):
    def fake_request(method, url, **kwargs):
        return DummyResponse(url)

    monkeypatch.setattr(http.requests, "request", fake_request)
    resp = http.safe_get("https://api.example.com/data", allowlist=["example.com"])
    assert isinstance(resp, DummyResponse)


def test_safe_request_blocks_unlisted_domain(monkeypatch):
    monkeypatch.setattr(
        http.requests, "request", lambda *a, **k: DummyResponse("blocked")
    )
    with pytest.raises(http.OutboundDomainError):
        http.safe_get("https://other.com/", allowlist=["example.com"])
    with pytest.raises(http.OutboundDomainError):
        http.safe_get("https://foobar.com/", allowlist=["bar.com"])


def test_safe_request_no_allowlist_allows_all(monkeypatch):
    monkeypatch.setattr(http.requests, "request", lambda *a, **k: DummyResponse("ok"))
    resp = http.safe_get("https://anywhere.test/path")
    assert isinstance(resp, DummyResponse)


def test_safe_request_invalid_scheme():
    with pytest.raises(ValueError):
        http.safe_get("ftp://example.com/file")


def test_safe_request_allowlist_is_case_insensitive(monkeypatch):
    monkeypatch.setattr(http.requests, "request", lambda *a, **k: DummyResponse("ok"))
    resp = http.safe_get("https://example.com", allowlist=["EXAMPLE.COM"])
    assert isinstance(resp, DummyResponse)


def test_safe_request_blocks_redirects(monkeypatch):
    monkeypatch.setattr(http.requests, "request", lambda *a, **k: DummyResponse("ok"))
    with pytest.raises(ValueError):
        http.safe_get(
            "https://example.com", allowlist=["example.com"], allow_redirects=True
        )


def test_safe_request_allows_ip_explicit(monkeypatch):
    monkeypatch.setattr(http.requests, "request", lambda *a, **k: DummyResponse("ok"))
    resp = http.safe_get("https://127.0.0.1/api", allowlist=["127.0.0.1"])
    assert isinstance(resp, DummyResponse)
    with pytest.raises(http.OutboundDomainError):
        http.safe_get("https://127.0.0.1/api", allowlist=["example.com"])


def test_env_allowlist(monkeypatch):
    monkeypatch.setenv(
        "OUTBOUND_ALLOWLIST",
        " example.com, ,  TEST.org  ",
    )
    monkeypatch.setattr(http.requests, "request", lambda *a, **k: DummyResponse("ok"))
    resp = http.safe_get("https://test.org/resource")
    assert isinstance(resp, DummyResponse)
    resp = http.safe_get("https://example.com/resource")
    assert isinstance(resp, DummyResponse)
    with pytest.raises(http.OutboundDomainError):
        http.safe_get("https://evil.net")
