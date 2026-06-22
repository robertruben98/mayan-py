"""Tests for the shared HTTP transport helpers."""

from __future__ import annotations

import httpx
import pytest

from mayan._transport import (
    RateLimitState,
    backoff_seconds,
    build_query,
    parse_response,
)
from mayan.exceptions import MayanAPIError, MayanRateLimitError


def test_build_query_drops_none_and_stringifies() -> None:
    out = build_query(a=1, b=None, c="x", d=True)
    assert out == {"a": "1", "c": "x", "d": "True"}


def test_parse_response_returns_json_on_2xx() -> None:
    resp = httpx.Response(200, json={"ok": True}, request=httpx.Request("GET", "https://x"))
    assert parse_response(resp) == {"ok": True}


def test_parse_response_raises_api_error_on_400_with_message() -> None:
    resp = httpx.Response(
        400,
        json={"message": "amountIn must be a number", "error": "Bad Request", "statusCode": 400},
        request=httpx.Request("GET", "https://x"),
    )
    with pytest.raises(MayanAPIError) as exc:
        parse_response(resp)
    assert exc.value.status_code == 400
    assert "amountIn" in str(exc.value)


def test_parse_response_reads_mayan_msg_field() -> None:
    # Mayan's 406 ROUTE_NOT_FOUND uses {"code", "msg"} rather than {"message"}.
    resp = httpx.Response(
        406,
        json={"code": "ROUTE_NOT_FOUND", "msg": "Route not found"},
        request=httpx.Request("GET", "https://x"),
    )
    with pytest.raises(MayanAPIError) as exc:
        parse_response(resp)
    assert exc.value.status_code == 406
    assert str(exc.value) == "Route not found"


def test_parse_response_handles_message_list() -> None:
    # NestJS validation errors put a list in "message".
    resp = httpx.Response(
        400,
        json={"message": ["amountIn must be a number"], "error": "Bad Request"},
        request=httpx.Request("GET", "https://x"),
    )
    with pytest.raises(MayanAPIError) as exc:
        parse_response(resp)
    assert "amountIn must be a number" in str(exc.value)


def test_parse_response_raises_rate_limit_on_429() -> None:
    resp = httpx.Response(
        429,
        headers={"retry-after": "12"},
        json={"message": "slow down"},
        request=httpx.Request("GET", "https://x"),
    )
    with pytest.raises(MayanRateLimitError) as exc:
        parse_response(resp)
    assert exc.value.status_code == 429
    assert exc.value.retry_after == 12.0


def test_rate_limit_state_updates_from_headers() -> None:
    state = RateLimitState()
    state.update(httpx.Headers({"ratelimit-limit": "100", "ratelimit-remaining": "5"}))
    assert state.current.limit == 100
    assert state.current.remaining == 5


def test_backoff_uses_exponential_when_no_header() -> None:
    resp = httpx.Response(429, request=httpx.Request("GET", "https://x"))
    assert backoff_seconds(0, resp) == 1.0
    assert backoff_seconds(1, resp) == 2.0
    assert backoff_seconds(2, resp) == 4.0
