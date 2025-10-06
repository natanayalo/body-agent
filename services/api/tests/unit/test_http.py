import pytest

from app.tools import http


class DummyResponse:
    def __init__(self, url: str):
        self.url = url


def test_safe_request_allows_exact_domain(monkeypatch):
    captured = {}

    def fake_request(method, url, headers=None, **kwargs):
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = headers
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


def test_safe_request_no_allowlist_allows_all(monkeypatch):
    monkeypatch.setattr(http.requests, "request", lambda *a, **k: DummyResponse("ok"))
    resp = http.safe_get("https://anywhere.test/path")
    assert isinstance(resp, DummyResponse)


def test_safe_request_invalid_scheme():
    with pytest.raises(ValueError):
        http.safe_get("ftp://example.com/file")


def test_env_allowlist(monkeypatch):
    monkeypatch.setenv("OUTBOUND_ALLOWLIST", "example.com, test.org")
    monkeypatch.setattr(http.requests, "request", lambda *a, **k: DummyResponse("ok"))
    resp = http.safe_get("https://test.org/resource")
    assert isinstance(resp, DummyResponse)
    with pytest.raises(http.OutboundDomainError):
        http.safe_get("https://evil.net")
