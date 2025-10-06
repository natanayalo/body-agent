from __future__ import annotations

import os
from typing import Iterable, Mapping, Any
from urllib.parse import urlparse
import ipaddress

import requests


class OutboundDomainError(RuntimeError):
    """Raised when a URL violates the configured outbound domain allow-list."""


def _parse_allowlist(spec: str | None = None) -> set[str]:
    raw = spec if spec is not None else os.getenv("OUTBOUND_ALLOWLIST", "")
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def _host_matches(host: str, allowed: Iterable[str]) -> bool:
    host_lc = host.lower()
    for entry in allowed:
        if host_lc == entry or host_lc.endswith(f".{entry}"):
            return True
    return False


def safe_request(
    method: str,
    url: str,
    *,
    allowlist: Iterable[str] | None = None,
    headers: Mapping[str, str] | None = None,
    **kwargs: Any,
) -> requests.Response:
    """Perform an HTTP request enforcing the outbound domain allow-list.

    If `allowlist` is provided, it overrides the value sourced from
    `OUTBOUND_ALLOWLIST`. When no allow-list entries exist, all domains are
    permitted. Subdomains automatically match their parent entry.
    """

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"Unsupported URL scheme: {parsed.scheme!r}")

    host = parsed.hostname or ""
    allowed_config = (
        {item.strip().lower() for item in allowlist if item.strip()}
        if allowlist is not None
        else _parse_allowlist()
    )

    if allowed_config:
        is_ip = False
        try:
            ipaddress.ip_address(host)
            is_ip = True
        except ValueError:
            pass

        if is_ip:
            if host.lower() not in allowed_config:
                raise OutboundDomainError(
                    f"IP '{host}' is not permitted (allowed: {', '.join(sorted(allowed_config))})"
                )
        else:
            if not _host_matches(host, allowed_config):
                raise OutboundDomainError(
                    f"Domain '{host}' is not permitted (allowed: {', '.join(sorted(allowed_config))})"
                )

    allow_redirects = kwargs.pop("allow_redirects", False)
    if allow_redirects:
        raise ValueError(
            "safe_request does not allow automatic redirects; handle redirects manually."
        )

    return requests.request(
        method.upper(), url, headers=headers, allow_redirects=False, **kwargs
    )


def safe_get(
    url: str,
    *,
    allowlist: Iterable[str] | None = None,
    headers: Mapping[str, str] | None = None,
    **kwargs: Any,
) -> requests.Response:
    """Convenience wrapper for GET requests that respect the domain allow-list."""

    return safe_request("GET", url, allowlist=allowlist, headers=headers, **kwargs)


__all__ = ["OutboundDomainError", "safe_request", "safe_get"]
