"""Helpers for browser-origin policy and SSRF-safe outbound URL handling."""

from __future__ import annotations

import ipaddress
import socket
from typing import Iterable
from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

IpAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


class _NoRedirectHandler(HTTPRedirectHandler):
    """Disable automatic redirects so each hop can be revalidated."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        """Return None so urllib surfaces redirects as HTTPError objects."""

        return None


_NO_REDIRECT_OPENER = build_opener(_NoRedirectHandler)


def _format_host(host: str) -> str:
    """Return one hostname/IP suitable for URL netloc reconstruction."""

    if ":" in host and not host.startswith("["):
        return f"[{host}]"
    return host


def _normalize_netloc(parts) -> str:
    """Rebuild one normalized netloc from parsed URL parts."""

    if not parts.hostname:
        raise ValueError("host is required")
    netloc = _format_host(parts.hostname.lower())
    if parts.port is not None:
        netloc = f"{netloc}:{parts.port}"
    return netloc


def normalize_origin(value: str, *, field_name: str = "origin") -> str:
    """Validate and normalize one browser origin string."""

    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} must not be empty.")
    try:
        parts = urlsplit(text)
        netloc = _normalize_netloc(parts)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid http/https origin.") from exc

    scheme = parts.scheme.lower()
    if scheme not in {"http", "https"}:
        raise ValueError(f"{field_name} must use http or https.")
    if parts.username is not None or parts.password is not None:
        raise ValueError(f"{field_name} must not include credentials.")
    if parts.path not in {"", "/"} or parts.query or parts.fragment:
        raise ValueError(f"{field_name} must not include path, query, or fragment.")
    return urlunsplit((scheme, netloc, "", "", ""))


def _resolve_host_ips(host: str) -> set[IpAddress]:
    """Resolve one hostname or IP literal to concrete IP addresses."""

    try:
        return {ipaddress.ip_address(host)}
    except ValueError:
        pass

    resolved: set[IpAddress] = set()
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("DNS resolution failed.") from exc
    for family, _type, _proto, _canonname, sockaddr in infos:
        if family == socket.AF_INET:
            resolved.add(ipaddress.ip_address(sockaddr[0]))
        elif family == socket.AF_INET6:
            resolved.add(ipaddress.ip_address(sockaddr[0]))
    if not resolved:
        raise ValueError("DNS resolution failed.")
    return resolved


def _ensure_public_ips(addresses: Iterable[IpAddress], *, field_name: str) -> None:
    """Reject non-public IP addresses for SSRF-sensitive outbound requests."""

    for address in addresses:
        if not address.is_global:
            raise ValueError(f"{field_name} must resolve to a public IP address.")


def validate_public_media_url(value: str, *, field_name: str = "url") -> str:
    """Validate and normalize one public http/https media URL."""

    text = value.strip()
    if not text:
        return ""

    try:
        parts = urlsplit(text)
        netloc = _normalize_netloc(parts)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid http/https URL.") from exc

    scheme = parts.scheme.lower()
    if scheme not in {"http", "https"}:
        raise ValueError(f"{field_name} must use http or https.")
    if parts.username is not None or parts.password is not None:
        raise ValueError(f"{field_name} must not include credentials.")
    _ensure_public_ips(_resolve_host_ips(parts.hostname or ""), field_name=field_name)
    return urlunsplit((scheme, netloc, parts.path, parts.query, parts.fragment))


def validate_media_reference(value: str, *, field_name: str = "url") -> str:
    """Validate one media reference as either a public URL or a site-relative path."""

    text = value.strip()
    if not text:
        return ""
    parts = urlsplit(text)
    if parts.scheme:
        return validate_public_media_url(text, field_name=field_name)
    if parts.netloc:
        raise ValueError(f"{field_name} must use http or https when specifying a host.")
    if not text.startswith("/"):
        raise ValueError(
            f"{field_name} must be an absolute http/https URL or site-relative path."
        )
    return text


def open_validated_public_url(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 6.0,
    max_redirects: int = 5,
):
    """Open one public media URL while revalidating each redirect target."""

    current_url = validate_public_media_url(url)
    request_headers = headers or {}
    for redirect_count in range(max_redirects + 1):
        request = Request(current_url, headers=request_headers)
        try:
            return _NO_REDIRECT_OPENER.open(request, timeout=timeout)
        except HTTPError as exc:
            try:
                if 300 <= exc.code < 400:
                    if redirect_count >= max_redirects:
                        raise ValueError("Too many redirects.")
                    location = str(exc.headers.get("Location") or "").strip()
                    if not location:
                        raise ValueError("Redirect location missing or invalid.")
                    current_url = validate_public_media_url(
                        urljoin(current_url, location)
                    )
                    continue
                raise
            finally:
                exc.close()
    raise ValueError("Too many redirects.")
