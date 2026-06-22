"""Live smoke tests against the real Mayan Finance API.

Deselected by default (``addopts = -m 'not integration'``). Run explicitly with:

    pytest -m integration

These hit keyless public endpoints; no API key required.
"""

from __future__ import annotations

import pytest

from mayan import MayanClient
from mayan.exceptions import MayanAPIError

pytestmark = pytest.mark.integration


# Well-known token addresses used by the live quote test.
USDC_SOLANA = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDC_ETHEREUM = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"


def test_live_tokens_solana() -> None:
    with MayanClient() as client:
        tokens = client.get_tokens(chain="solana")
    assert "solana" in tokens
    assert len(tokens["solana"]) > 0
    # native SOL is always present
    assert any(t.symbol == "SOL" for t in tokens["solana"])


def test_live_get_quotes_usdc_solana_to_ethereum() -> None:
    """Exercise the headline quote path against production.

    This parses the real ``QuoteResponse`` (including ``minimumSdkVersion``,
    which the API returns as a list), so any modeled-field type drift fails the
    test instead of crashing users.
    """
    with MayanClient(referer="mayan-py-tests") as client:
        try:
            resp = client.get_quotes(
                amount="100",
                from_token=USDC_SOLANA,
                from_chain="solana",
                to_token=USDC_ETHEREUM,
                to_chain="ethereum",
                slippage_bps=300,
            )
        except MayanAPIError as exc:
            # A transient absence of routes (HTTP 406) shouldn't fail the suite;
            # only a modeled-field shape break (ValidationError) should.
            if exc.status_code == 406:
                pytest.skip("no route available right now (406 ROUTE_NOT_FOUND)")
            raise
    assert len(resp.quotes) > 0
    quote = resp.quotes[0]
    assert quote.type
    assert quote.expected_amount_out is not None
    assert quote.expected_amount_out > 0
