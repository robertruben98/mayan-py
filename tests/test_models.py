"""Tests for the pydantic models that parse Mayan API payloads."""

from __future__ import annotations

from mayan.models import Quote, QuoteResponse, SwapStatus, Token

from .conftest import QUOTE_RESPONSE, SOL_TOKEN, STATUS_RESPONSE


def test_token_parses_core_fields() -> None:
    token = Token.model_validate(SOL_TOKEN)
    assert token.symbol == "USDC"
    assert token.mint == "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
    assert token.contract == "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
    assert token.chain_id == 0
    assert token.w_chain_id == 1
    assert token.decimals == 6
    assert token.standard == "spl"
    assert token.logo_uri == "https://statics.mayan.finance/USDC.png"


def test_token_keeps_unknown_extra_fields() -> None:
    # extra="allow" keeps fields not modelled explicitly (forward-compatible).
    token = Token.model_validate({**SOL_TOKEN, "brandNewField": 123})
    assert token.model_dump()["brandNewField"] == 123


def test_quote_response_parses_list_and_min_sdk() -> None:
    resp = QuoteResponse.model_validate(QUOTE_RESPONSE)
    # The live API sends minimumSdkVersion as a list ([7, 0, 0]); it is
    # normalized to a dotted version string.
    assert resp.minimum_sdk_version == "7.0.0"
    assert len(resp.quotes) == 1
    assert isinstance(resp.quotes[0], Quote)


def test_quote_response_minimum_sdk_version_accepts_list() -> None:
    # Regression: the price API returns minimumSdkVersion as a JSON array of
    # version components, not a string. Parsing must not raise (this crashed
    # get_quote/get_quotes against production before the fix).
    resp = QuoteResponse.model_validate({"quotes": [], "minimumSdkVersion": [7, 0, 0]})
    assert resp.minimum_sdk_version == "7.0.0"


def test_quote_response_minimum_sdk_version_accepts_string() -> None:
    # A plain string is still accepted unchanged (forward/backward compatible).
    resp = QuoteResponse.model_validate({"quotes": [], "minimumSdkVersion": "9_0_0"})
    assert resp.minimum_sdk_version == "9_0_0"


def test_quote_response_minimum_sdk_version_absent() -> None:
    resp = QuoteResponse.model_validate({"quotes": []})
    assert resp.minimum_sdk_version is None


def test_quote_headline_fields() -> None:
    quote = Quote.model_validate(QUOTE_RESPONSE["quotes"][0])
    assert quote.type == "MCTP"
    assert quote.from_chain == "solana"
    assert quote.to_chain == "ethereum"
    assert quote.slippage_bps == 300
    assert quote.expected_amount_out == 97.970857
    assert quote.expected_amount_out_base_units == "97970857"
    assert quote.min_amount_out == 95.09137
    assert quote.eta_seconds == 60
    assert quote.client_eta == "1 min"
    # nested tokens are parsed into Token models
    assert isinstance(quote.from_token, Token)
    assert quote.from_token.symbol == "USDC"
    assert isinstance(quote.to_token, Token)
    assert quote.to_token.standard == "erc20"


def test_swap_status_parses_and_exposes_state() -> None:
    status = SwapStatus.model_validate(STATUS_RESPONSE)
    assert status.id == "bfcd28f8-9a62-4718-a293-e3001b71a826"
    assert status.status == "REDEEMED_ON_EVM_WITH_FEE"
    assert status.client_status == "COMPLETED"
    assert status.source_tx_hash is not None
    assert status.source_tx_hash.startswith("0x5eaa")
    assert status.service == "MCTP_FAST_BRIDGE"
    assert status.from_amount == "202.999999"


def test_swap_status_terminal_helpers_completed() -> None:
    status = SwapStatus.model_validate(STATUS_RESPONSE)
    assert status.is_completed is True
    assert status.is_refunded is False
    assert status.is_terminal is True


def test_swap_status_terminal_helpers_refunded() -> None:
    status = SwapStatus.model_validate({**STATUS_RESPONSE, "clientStatus": "REFUNDED"})
    assert status.is_completed is False
    assert status.is_refunded is True
    assert status.is_terminal is True


def test_swap_status_terminal_helpers_inprogress() -> None:
    status = SwapStatus.model_validate({**STATUS_RESPONSE, "clientStatus": "INPROGRESS"})
    assert status.is_completed is False
    assert status.is_refunded is False
    assert status.is_terminal is False
