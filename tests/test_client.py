"""Tests for the synchronous MayanClient using mocked HTTP (respx)."""

from __future__ import annotations

import httpx
import pytest
import respx

from mayan import MayanClient
from mayan.exceptions import MayanAPIError, MayanRateLimitError
from mayan.models import Quote, QuoteResponse, SwapStatus, Token

from .conftest import (
    QUOTE_RESPONSE,
    STATUS_RESPONSE,
    SWAPS_LIST_RESPONSE,
    TOKENS_RESPONSE,
)

BASE = "https://price-api.mayan.finance"
STATUS_BASE = "https://explorer-api.mayan.finance"


def test_default_base_urls_and_no_auth_header() -> None:
    client = MayanClient()
    assert client.base_url == BASE
    assert client.status_base_url == STATUS_BASE
    assert "x-api-key" not in client._http.headers


def test_api_key_sets_header() -> None:
    client = MayanClient(api_key="secret-key")
    assert client._http.headers["x-api-key"] == "secret-key"


def test_custom_base_url_normalizes_trailing_slash() -> None:
    client = MayanClient(base_url="https://staging.example.com/", api_key="k")
    assert client.base_url == "https://staging.example.com"


def test_referer_header_sent_by_default() -> None:
    client = MayanClient()
    assert client._http.headers["referer"] == "mayan-py"


@respx.mock
def test_get_quote_returns_best_quote_and_sends_required_params() -> None:
    route = respx.get(f"{BASE}/v3/quote").mock(
        return_value=httpx.Response(200, json=QUOTE_RESPONSE)
    )
    client = MayanClient()
    quote = client.get_quote(
        amount="100",
        from_token="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        from_chain="solana",
        to_token="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        to_chain="ethereum",
        slippage_bps=300,
    )
    assert isinstance(quote, Quote)
    assert quote.type == "MCTP"
    assert quote.expected_amount_out == 97.970857

    params = httpx.URL(route.calls.last.request.url).params
    assert params["amountIn"] == "100"
    assert params["fromToken"] == "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
    assert params["fromChain"] == "solana"
    assert params["toToken"] == "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
    assert params["toChain"] == "ethereum"
    assert params["slippageBps"] == "300"
    # sdkVersion is required by the API for the request to be valid.
    assert "sdkVersion" in params


@respx.mock
def test_get_quote_enables_protocol_flags_by_default() -> None:
    # Without protocol flags Mayan returns 406 ROUTE_NOT_FOUND, so the client
    # must enable them by default.
    route = respx.get(f"{BASE}/v3/quote").mock(
        return_value=httpx.Response(200, json=QUOTE_RESPONSE)
    )
    client = MayanClient()
    client.get_quote(
        amount="100",
        from_token="A",
        from_chain="solana",
        to_token="B",
        to_chain="ethereum",
    )
    params = httpx.URL(route.calls.last.request.url).params
    assert params["swift"] == "true"
    assert params["mctp"] == "true"
    assert params["wormhole"] == "true"
    assert params["fastMctp"] == "true"


@respx.mock
def test_get_quote_uses_amount_in_base_units_when_given() -> None:
    route = respx.get(f"{BASE}/v3/quote").mock(
        return_value=httpx.Response(200, json=QUOTE_RESPONSE)
    )
    client = MayanClient()
    client.get_quote(
        amount_base_units="100000000",
        from_token="A",
        from_chain="solana",
        to_token="B",
        to_chain="ethereum",
    )
    params = httpx.URL(route.calls.last.request.url).params
    assert params["amountIn64"] == "100000000"
    assert "amountIn" not in params


def test_get_quote_requires_an_amount() -> None:
    client = MayanClient()
    with pytest.raises(ValueError, match="amount"):
        client.get_quote(from_token="A", from_chain="solana", to_token="B", to_chain="ethereum")


@respx.mock
def test_get_quotes_returns_full_response() -> None:
    respx.get(f"{BASE}/v3/quote").mock(return_value=httpx.Response(200, json=QUOTE_RESPONSE))
    client = MayanClient()
    resp = client.get_quotes(
        amount="100",
        from_token="A",
        from_chain="solana",
        to_token="B",
        to_chain="ethereum",
    )
    assert isinstance(resp, QuoteResponse)
    # The fixture mirrors the live array form ([7, 0, 0]) -> normalized string.
    assert resp.minimum_sdk_version == "7.0.0"
    assert len(resp.quotes) == 1


@respx.mock
def test_get_quote_raises_when_no_route() -> None:
    respx.get(f"{BASE}/v3/quote").mock(
        return_value=httpx.Response(200, json={"quotes": [], "minimumSdkVersion": "9_0_0"})
    )
    client = MayanClient()
    with pytest.raises(MayanAPIError, match="No route"):
        client.get_quote(
            amount="100", from_token="A", from_chain="solana", to_token="B", to_chain="ethereum"
        )


@respx.mock
def test_get_tokens_returns_chain_keyed_dict() -> None:
    route = respx.get(f"{BASE}/v3/tokens").mock(
        return_value=httpx.Response(200, json=TOKENS_RESPONSE)
    )
    client = MayanClient()
    tokens = client.get_tokens(chain="solana")
    assert set(tokens.keys()) == {"solana"}
    assert all(isinstance(t, Token) for t in tokens["solana"])
    assert tokens["solana"][0].symbol == "SOL"
    params = httpx.URL(route.calls.last.request.url).params
    assert params["chain"] == "solana"


@respx.mock
def test_get_swap_status() -> None:
    route = respx.get(f"{STATUS_BASE}/v3/swap/trx/0x5eaa").mock(
        return_value=httpx.Response(200, json=STATUS_RESPONSE)
    )
    client = MayanClient()
    status = client.get_swap_status(tx_hash="0x5eaa")
    assert isinstance(status, SwapStatus)
    assert status.is_completed
    assert status.is_terminal
    # the status call hits the explorer host, not the price host
    assert route.calls.last.request.url.host == "explorer-api.mayan.finance"


@respx.mock
def test_list_swaps_by_trader() -> None:
    route = respx.get(f"{STATUS_BASE}/v3/swaps").mock(
        return_value=httpx.Response(200, json=SWAPS_LIST_RESPONSE)
    )
    client = MayanClient()
    swaps = client.list_swaps(trader="0x2fd87ACfee01B5311fDD33a10866fFd14c4aE36B", limit=10)
    assert len(swaps) == 1
    assert isinstance(swaps[0], SwapStatus)
    params = httpx.URL(route.calls.last.request.url).params
    assert params["trader"] == "0x2fd87ACfee01B5311fDD33a10866fFd14c4aE36B"
    assert params["limit"] == "10"


@respx.mock
def test_api_error_raised_on_400() -> None:
    respx.get(f"{BASE}/v3/quote").mock(
        return_value=httpx.Response(400, json={"message": "amountIn must be a number"})
    )
    client = MayanClient()
    with pytest.raises(MayanAPIError) as exc:
        client.get_quote(
            amount="bad", from_token="A", from_chain="solana", to_token="B", to_chain="ethereum"
        )
    assert exc.value.status_code == 400


@respx.mock
def test_406_route_not_found_surfaces_message() -> None:
    respx.get(f"{BASE}/v3/quote").mock(
        return_value=httpx.Response(406, json={"code": "ROUTE_NOT_FOUND", "msg": "Route not found"})
    )
    client = MayanClient()
    with pytest.raises(MayanAPIError) as exc:
        client.get_quote(
            amount="1", from_token="A", from_chain="solana", to_token="B", to_chain="ethereum"
        )
    assert exc.value.status_code == 406
    assert str(exc.value) == "Route not found"


@respx.mock
def test_429_then_success_retries_with_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []
    import mayan._transport as transport

    monkeypatch.setattr(transport.time, "sleep", lambda s: sleeps.append(s))

    route = respx.get(f"{BASE}/v3/tokens")
    route.side_effect = [
        httpx.Response(429, headers={"retry-after": "1"}, json={"message": "slow down"}),
        httpx.Response(200, json=TOKENS_RESPONSE),
    ]
    client = MayanClient(max_retries=2)
    tokens = client.get_tokens(chain="solana")
    assert "solana" in tokens
    assert route.call_count == 2
    assert sleeps and sleeps[0] >= 1.0


@respx.mock
def test_429_raises_after_retries_exhausted() -> None:
    respx.get(f"{BASE}/v3/tokens").mock(
        return_value=httpx.Response(429, headers={"retry-after": "5"}, json={"message": "no"})
    )
    client = MayanClient(max_retries=0)
    with pytest.raises(MayanRateLimitError) as exc:
        client.get_tokens(chain="solana")
    assert exc.value.retry_after == 5.0


@respx.mock
def test_poll_swap_status_until_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    import mayan._transport as transport

    monkeypatch.setattr(transport.time, "sleep", lambda s: None)
    route = respx.get(f"{STATUS_BASE}/v3/swap/trx/0x5eaa")
    route.side_effect = [
        httpx.Response(200, json={**STATUS_RESPONSE, "clientStatus": "INPROGRESS"}),
        httpx.Response(200, json={**STATUS_RESPONSE, "clientStatus": "COMPLETED"}),
    ]
    client = MayanClient()
    status = client.poll_swap_status(tx_hash="0x5eaa", interval=0.01)
    assert status.is_completed
    assert route.call_count == 2


@respx.mock
def test_poll_swap_status_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    import mayan._transport as transport

    monkeypatch.setattr(transport.time, "sleep", lambda s: None)
    respx.get(f"{STATUS_BASE}/v3/swap/trx/0x5eaa").mock(
        return_value=httpx.Response(200, json={**STATUS_RESPONSE, "clientStatus": "INPROGRESS"})
    )
    client = MayanClient()
    with pytest.raises(TimeoutError):
        client.poll_swap_status(tx_hash="0x5eaa", interval=1.0, timeout=2.0)


def test_context_manager_closes() -> None:
    with MayanClient() as client:
        assert client._http.is_closed is False
    assert client._http.is_closed is True


@respx.mock
def test_injected_http_client_is_used() -> None:
    respx.get("https://proxy.internal/v3/tokens").mock(
        return_value=httpx.Response(200, json=TOKENS_RESPONSE)
    )
    http = httpx.Client(base_url="https://proxy.internal")
    client = MayanClient(http_client=http)
    tokens = client.get_tokens(chain="solana")
    assert "solana" in tokens


def test_injected_http_client_warns_on_conflicting_args() -> None:
    http = httpx.Client(base_url="https://proxy.internal")
    with pytest.warns(UserWarning, match="http_client"):
        client = MayanClient(base_url="https://other.example", http_client=http)
    assert client.base_url == "https://proxy.internal"


def test_custom_referer() -> None:
    client = MayanClient(referer="my-app")
    assert client._http.headers["referer"] == "my-app"


@respx.mock
def test_get_quote_passes_referrer_and_gas_drop() -> None:
    route = respx.get(f"{BASE}/v3/quote").mock(
        return_value=httpx.Response(200, json=QUOTE_RESPONSE)
    )
    client = MayanClient()
    client.get_quote(
        amount="100",
        from_token="A",
        from_chain="solana",
        to_token="B",
        to_chain="ethereum",
        referrer="0xref",
        referrer_bps=5,
        gas_drop=0.01,
    )
    params = httpx.URL(route.calls.last.request.url).params
    assert params["referrer"] == "0xref"
    assert params["referrerBps"] == "5"
    assert params["gasDrop"] == "0.01"
