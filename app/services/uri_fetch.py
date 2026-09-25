"""Fetches a document from an external URL for Factory.LoadFromUri.

SECURITY NOTE: this is a best-effort SSRF guard (scheme allowlist + DNS-resolved
private/loopback/link-local IP block, redirects disabled), not an exhaustive one.
It does not protect against DNS rebinding between the check and the actual
request, or against a target that itself proxies to an internal address. Harden
this (e.g. a strict destination allowlist, or fetch through an egress proxy)
before exposing LoadFromUri to untrusted callers in production.
"""
import ipaddress
import socket
from typing import Optional, Tuple
from urllib.parse import urlparse

import requests

from app.services.errors import ConversionError

ALLOWED_SCHEMES = {"http", "https"}
MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024
REQUEST_TIMEOUT_SECONDS = 30


def _is_private_host(hostname: str) -> bool:
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return True  # can't resolve -> refuse rather than risk it
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return True
    return False


def fetch_uri_bytes(uri: str) -> Tuple[bytes, Optional[str]]:
    parsed = urlparse(uri)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise ConversionError(f"Unsupported URI scheme: {parsed.scheme!r}", status_code=400)
    if not parsed.hostname:
        raise ConversionError("URI must include a host", status_code=400)
    if _is_private_host(parsed.hostname):
        raise ConversionError("Refusing to load from a private/internal address", status_code=400)

    try:
        response = requests.get(uri, timeout=REQUEST_TIMEOUT_SECONDS, stream=True, allow_redirects=False)
        response.raise_for_status()
        content = response.raw.read(MAX_DOWNLOAD_BYTES + 1, decode_content=True)
        if len(content) > MAX_DOWNLOAD_BYTES:
            raise ConversionError("Document exceeds maximum allowed download size", status_code=413)
        mime_type = (response.headers.get("Content-Type") or "").split(";")[0].strip() or None
        return content, mime_type
    except requests.RequestException as exc:
        raise ConversionError(f"Failed to fetch document from URI: {exc}", cause=exc) from exc
