"""Get a cross-chain swap quote in a few lines.

Run with: python examples/quote.py
"""

from __future__ import annotations

from mayan import MayanClient

# USDC on Solana -> USDC on Ethereum
USDC_SOLANA = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDC_ETHEREUM = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"


def main() -> None:
    with MayanClient(referer="mayan-py-example") as client:
        quote = client.get_quote(
            amount="100",  # 100 USDC, in whole units
            from_token=USDC_SOLANA,
            from_chain="solana",
            to_token=USDC_ETHEREUM,
            to_chain="ethereum",
            slippage_bps=300,
        )

    print(f"Protocol:        {quote.type}")
    print(
        f"Expected out:    {quote.expected_amount_out} {quote.to_token and quote.to_token.symbol}"
    )
    print(f"Min received:    {quote.min_received}")
    print(f"ETA:             {quote.client_eta} ({quote.eta_seconds}s)")


if __name__ == "__main__":
    main()
