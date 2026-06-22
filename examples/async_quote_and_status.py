"""Async quote, then poll a swap to a terminal state.

Run with: python examples/async_quote_and_status.py
"""

from __future__ import annotations

import asyncio

from mayan import AsyncMayanClient

USDC_SOLANA = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDC_ETHEREUM = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"


async def main() -> None:
    async with AsyncMayanClient(referer="mayan-py-example") as client:
        # 1. Fetch the best route.
        quote = await client.get_quote(
            amount="100",
            from_token=USDC_SOLANA,
            from_chain="solana",
            to_token=USDC_ETHEREUM,
            to_chain="ethereum",
        )
        print(f"Best route: {quote.type}, expected out {quote.expected_amount_out}")

        # 2. After you broadcast the source transaction, poll it to completion.
        #    Replace with your real source-chain transaction hash.
        source_tx_hash = "0xYOUR_SOURCE_TX_HASH"
        if source_tx_hash.startswith("0xYOUR"):
            print("Set source_tx_hash to a real hash to poll a swap.")
            return

        final = await client.poll_swap_status(tx_hash=source_tx_hash)
        print(f"Final status: {final.client_status} (detail: {final.status})")


if __name__ == "__main__":
    asyncio.run(main())
