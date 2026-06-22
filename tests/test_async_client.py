"""Tests for the asynchronous AsyncMayanClient using mocked HTTP (respx)."""

from __future__ import annotations

import httpx
import pytest
import respx

from mayan import AsyncMayanClient
from mayan.exceptions import MayanAPIError
from mayan.models import Quote, QuoteResponse, SwapStatus, Token

from .conftest import QUOTE_RESPONSE, STATUS_RESPONSE, SWAPS_LIST_RESPONSE, TOKENS_RESPONSE

BASE = "https://price-api.mayan.finance"
STATUS_BASE = "https://explorer-api.mayan.finance"


@respx.mock
async def test_async_get_quote() -> None:
    route = respx.get(f"{BASE}/v3/quote").mock(
        return_value=httpx.Response(200, json=QUOTE_RESPONSE)
    )
    async with AsyncMayanClient() as client:
        quote = await client.get_quote(
            amount="100",
            from_token="A",
            from_chain="solana",
            to_token="B",
            to_chain="ethereum",
        )
    assert isinstance(quote, Quote)
    assert quote.type == "MCTP"
    params = httpx.URL(route.calls.last.request.url).params
    assert params["amountIn"] == "100"
    assert params["swift"] == "true"


@respx.mock
async def test_async_get_quotes_full_response() -> None:
    respx.get(f"{BASE}/v3/quote").mock(return_value=httpx.Response(200, json=QUOTE_RESPONSE))
    async with AsyncMayanClient() as client:
        resp = await client.get_quotes(
            amount="100", from_token="A", from_chain="solana", to_token="B", to_chain="ethereum"
        )
    assert isinstance(resp, QuoteResponse)
    assert len(resp.quotes) == 1


async def test_async_get_quote_requires_amount() -> None:
    async with AsyncMayanClient() as client:
        with pytest.raises(ValueError, match="amount"):
            await client.get_quote(
                from_token="A", from_chain="solana", to_token="B", to_chain="ethereum"
            )


@respx.mock
async def test_async_get_quote_raises_when_no_route() -> None:
    respx.get(f"{BASE}/v3/quote").mock(
        return_value=httpx.Response(200, json={"quotes": [], "minimumSdkVersion": "9_0_0"})
    )
    async with AsyncMayanClient() as client:
        with pytest.raises(MayanAPIError, match="No route"):
            await client.get_quote(
                amount="1", from_token="A", from_chain="solana", to_token="B", to_chain="ethereum"
            )


@respx.mock
async def test_async_get_tokens() -> None:
    respx.get(f"{BASE}/v3/tokens").mock(return_value=httpx.Response(200, json=TOKENS_RESPONSE))
    async with AsyncMayanClient() as client:
        tokens = await client.get_tokens(chain="solana")
    assert "solana" in tokens
    assert isinstance(tokens["solana"][0], Token)


@respx.mock
async def test_async_get_swap_status_hits_explorer_host() -> None:
    route = respx.get(f"{STATUS_BASE}/v3/swap/trx/0x5eaa").mock(
        return_value=httpx.Response(200, json=STATUS_RESPONSE)
    )
    async with AsyncMayanClient() as client:
        status = await client.get_swap_status(tx_hash="0x5eaa")
    assert isinstance(status, SwapStatus)
    assert status.is_completed
    assert route.calls.last.request.url.host == "explorer-api.mayan.finance"


@respx.mock
async def test_async_list_swaps() -> None:
    respx.get(f"{STATUS_BASE}/v3/swaps").mock(
        return_value=httpx.Response(200, json=SWAPS_LIST_RESPONSE)
    )
    async with AsyncMayanClient() as client:
        swaps = await client.list_swaps(trader="0xabc")
    assert len(swaps) == 1
    assert isinstance(swaps[0], SwapStatus)


@respx.mock
async def test_async_poll_swap_status(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    async def _no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", _no_sleep)
    route = respx.get(f"{STATUS_BASE}/v3/swap/trx/0x5eaa")
    route.side_effect = [
        httpx.Response(200, json={**STATUS_RESPONSE, "clientStatus": "INPROGRESS"}),
        httpx.Response(200, json={**STATUS_RESPONSE, "clientStatus": "REFUNDED"}),
    ]
    async with AsyncMayanClient() as client:
        status = await client.poll_swap_status(tx_hash="0x5eaa", interval=0.01)
    assert status.is_refunded
    assert route.call_count == 2


async def test_async_context_manager_closes() -> None:
    async with AsyncMayanClient() as client:
        assert client._http.is_closed is False
    assert client._http.is_closed is True
