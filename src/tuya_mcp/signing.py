"""Tuya OpenAPI request signing (HMAC-SHA256).

Reference: https://developer.tuya.com/en/docs/iot/new-singnature?id=Kbw0q34cs2e5g
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping, Sequence

EMPTY_BODY_SHA256 = hashlib.sha256(b"").hexdigest()

QueryValue = str | int | bool


def build_url(path: str, params: Mapping[str, QueryValue] | None = None) -> str:
    """Return the path with its query string, keys sorted as required by Tuya."""
    if not params:
        return path
    query = "&".join(f"{key}={_query_value(params[key])}" for key in sorted(params))
    return f"{path}?{query}"


def _query_value(value: QueryValue) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def string_to_sign(
    method: str,
    url: str,
    body: bytes = b"",
    signed_headers: Sequence[tuple[str, str]] = (),
) -> str:
    """Build the canonical stringToSign: method, body hash, signed headers, URL."""
    content_sha256 = hashlib.sha256(body).hexdigest()
    headers = "".join(f"{key}:{value}\n" for key, value in signed_headers)
    return f"{method.upper()}\n{content_sha256}\n{headers}\n{url}"


def sign(
    *,
    client_id: str,
    secret: str,
    t: str,
    string_to_sign: str,
    access_token: str = "",
    nonce: str = "",
) -> str:
    """Compute the uppercase hex HMAC-SHA256 signature.

    Token requests pass no access_token; business requests pass the cached one.
    """
    message = client_id + access_token + t + nonce + string_to_sign
    digest = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    return digest.upper()
