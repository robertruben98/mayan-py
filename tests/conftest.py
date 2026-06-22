"""Shared fixtures: realistic Mayan Finance API payloads (captured from live calls).

The shapes here mirror real responses observed against
``https://price-api.mayan.finance`` (quote, tokens) and
``https://explorer-api.mayan.finance`` (swap status), trimmed to the fields the
models care about while keeping a few extras so ``extra="allow"`` is exercised.
"""

from __future__ import annotations

from typing import Any

import pytest

# A real /v3/tokens?chain=solana entry (native SOL), as keyed by chain name.
SOL_TOKEN: dict[str, Any] = {
    "name": "USD Coin",
    "standard": "spl",
    "symbol": "USDC",
    "mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "verified": True,
    "contract": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "chainId": 0,
    "wChainId": 1,
    "decimals": 6,
    "logoURI": "https://statics.mayan.finance/USDC.png",
    "coingeckoId": "usd-coin",
    "realOriginChainId": 1,
    "supportsPermit": False,
    "hasAuction": True,
}

TOKENS_RESPONSE: dict[str, Any] = {
    "solana": [
        {
            "name": "SOL",
            "standard": "native",
            "symbol": "SOL",
            "mint": "So11111111111111111111111111111111111111112",
            "verified": True,
            "contract": "0x0000000000000000000000000000000000000000",
            "chainId": 0,
            "wChainId": 1,
            "decimals": 9,
            "logoURI": "https://statics.mayan.finance/SOL.png",
            "coingeckoId": "solana",
            "supportsPermit": False,
            "hasAuction": True,
        },
        SOL_TOKEN,
    ],
}

# A real /v3/quote response (100 USDC Solana -> USDC Ethereum via MCTP), trimmed.
QUOTE_RESPONSE: dict[str, Any] = {
    "quotes": [
        {
            "type": "MCTP",
            "fromChain": "solana",
            "toChain": "ethereum",
            "fromToken": SOL_TOKEN,
            "toToken": {
                "name": "USD Coin",
                "standard": "erc20",
                "symbol": "USDC",
                "mint": "",
                "contract": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
                "chainId": 1,
                "wChainId": 2,
                "decimals": 6,
                "verified": True,
            },
            "slippageBps": 300,
            "effectiveAmountIn": 100,
            "effectiveAmountIn64": "100000000",
            "expectedAmountOut": 97.970857,
            "expectedAmountOutBaseUnits": "97970857",
            "minAmountOut": 95.09137,
            "minAmountOutBaseUnits": "95091370",
            "minReceived": 95.09137,
            "minReceivedBaseUnits": "95091370",
            "price": 0.979945990614606,
            "eta": 1,
            "etaSeconds": 60,
            "clientEta": "1 min",
            "gasDrop": 0,
            "referrerBps": 0,
            "redeemRelayerFee64": "2029143",
            "swapRelayerFee64": "153052",
            "deadline64": "1782118451",
            "hasAuction": False,
            "gasless": False,
            "route": None,
        }
    ],
    # The live price API returns this as a JSON array of version components,
    # NOT a string (verified live: [7, 0, 0]).
    "minimumSdkVersion": [7, 0, 0],
}

# A real /v3/swap/trx/{hash} response (MCTP fast bridge, completed), trimmed.
STATUS_RESPONSE: dict[str, Any] = {
    "id": "bfcd28f8-9a62-4718-a293-e3001b71a826",
    "trader": "0x2fd87ACfee01B5311fDD33a10866fFd14c4aE36B",
    "sourceTxHash": "0x5eaa48d2990be01a6bc0b269054674edbc2c1086bd3a1d68a5d6cedb2ec23835",
    "sourceChain": "24",
    "destChain": "47",
    "status": "REDEEMED_ON_EVM_WITH_FEE",
    "clientStatus": "COMPLETED",
    "service": "MCTP_FAST_BRIDGE",
    "fromAmount": "202.999999",
    "toAmount": "202.5",
    "fromTokenAddress": "0x0b2c639c533813f4aa9d7837caf62653d097ff85",
    "fromTokenSymbol": "USDC",
    "toTokenAddress": "0xb8ce59fc3717ada4c02eadf9682a9e934f625ebb",
    "toTokenSymbol": "USD₮0",
    "orderHash": "0xabc123",
    "fulfillTxHash": "0xdef456",
    "initiatedAt": "2026-06-22T08:00:00.000Z",
}

# A /v3/swaps?trader=... list response.
SWAPS_LIST_RESPONSE: dict[str, Any] = {
    "data": [STATUS_RESPONSE],
    "metadata": {"count": 1},
}


@pytest.fixture
def tokens_response() -> dict[str, Any]:
    return TOKENS_RESPONSE


@pytest.fixture
def quote_response() -> dict[str, Any]:
    return QUOTE_RESPONSE


@pytest.fixture
def status_response() -> dict[str, Any]:
    return STATUS_RESPONSE
