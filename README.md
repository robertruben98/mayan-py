# mayan-py

[![CI](https://github.com/robertruben98/mayan-py/actions/workflows/ci.yml/badge.svg)](https://github.com/robertruben98/mayan-py/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/mayan-py.svg)](https://pypi.org/project/mayan-py/)
[![Python versions](https://img.shields.io/pypi/pyversions/mayan-py.svg)](https://pypi.org/project/mayan-py/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/robertruben98/mayan-py/blob/main/LICENSE)

A typed Python client for the [Mayan Finance API](https://docs.mayan.finance)
— cross-chain swaps and bridging across **Solana, EVM chains and Sui** (and more:
Aptos, Sui, Base, Arbitrum, Optimism, Polygon, BNB, Avalanche, Linea, Sonic…).

The headline call: `get_quote()` returns the best cross-chain route — expected
output, fees and ETA — across all of Mayan's protocols (MCTP, Swift, Wormhole).

- Sync (`MayanClient`) and async (`AsyncMayanClient`) clients on top of `httpx`.
- All responses parsed into `pydantic` v2 models with full type hints (`py.typed`).
  Models tolerate unknown fields, so they keep working as the API evolves.
- Multi-ecosystem by design: addresses and raw amounts are strings, so Solana
  mints, EVM contracts and Sui types all round-trip without precision loss.
- Status tracking with `poll_swap_status()` — polls a swap to a terminal
  (`COMPLETED` / `REFUNDED`) state with exponential backoff.

## Install

```bash
pip install mayan-py
```

## Quickstart — a cross-chain quote (keyless, a few lines)

```python
from mayan import MayanClient

quote = MayanClient().get_quote(
    amount="100",                                                  # 100 USDC (whole units)
    from_token="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",     # USDC (Solana)
    from_chain="solana",
    to_token="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",         # USDC (Ethereum)
    to_chain="ethereum",
)
print(quote.type, quote.expected_amount_out, quote.client_eta)     # MCTP 97.97 "1 min"
```

Pass `amount_base_units="100000000"` instead of `amount` to specify the input in
the token's smallest unit. Use `get_quotes(...)` to get **every** candidate route
(one per protocol) plus the minimum SDK version, rather than just the best one.

## Supported tokens

```python
tokens = MayanClient().get_tokens(chain="solana")   # {"solana": [Token, ...]}
sol = next(t for t in tokens["solana"] if t.symbol == "SOL")
print(sol.mint, sol.decimals)
```

## Track a swap to completion

After you broadcast the source-chain transaction, poll its status (this hits
Mayan's explorer API):

```python
client = MayanClient()
status = client.get_swap_status(tx_hash="0x5eaa...")     # one-shot lookup
print(status.client_status, status.status)               # "COMPLETED", "REDEEMED_ON_EVM_WITH_FEE"

final = client.poll_swap_status(tx_hash="0x5eaa...")     # blocks until terminal
assert final.is_terminal                                  # is_completed or is_refunded
```

## Async

```python
import asyncio
from mayan import AsyncMayanClient

async def main():
    async with AsyncMayanClient() as client:
        return await client.get_tokens(chain="solana")

asyncio.run(main())
```

The async client mirrors the sync one method-for-method.

## Configuration

`MayanClient` / `AsyncMayanClient` accept:

| Argument          | Default                                | Purpose                                                  |
| ----------------- | -------------------------------------- | -------------------------------------------------------- |
| `referer`         | `"mayan-py"`                           | Required `referer` header; set it to identify your app.  |
| `api_key`         | `None`                                 | Optional API key (all endpoints work keyless).           |
| `base_url`        | `https://price-api.mayan.finance`      | Price API host (quotes, tokens).                         |
| `status_base_url` | `https://explorer-api.mayan.finance`   | Explorer API host (swap status).                         |
| `sdk_version`     | `"10_0_0"`                             | `sdkVersion` the API requires to serve quotes/tokens.    |
| `timeout`         | `30.0`                                 | Per-request timeout (seconds).                            |
| `max_retries`     | `3`                                    | 429 retries before raising `MayanRateLimitError`.        |
| `http_client`     | `None`                                 | Bring your own `httpx.Client`/`AsyncClient`.             |

## Errors

All library errors subclass `MayanError`:

- `MayanAPIError` — non-2xx response (e.g. HTTP 406 `ROUTE_NOT_FOUND` when no
  route exists). Carries `status_code` and `response_body`.
- `MayanRateLimitError` — HTTP 429 after retries are exhausted; carries
  `retry_after`.

## Examples

See [`examples/`](examples/): `quote.py` and `async_quote_and_status.py`.

## Development

```bash
pip install -e '.[dev]'
ruff check .
mypy
pytest                 # unit tests (live tests deselected)
pytest -m integration  # live keyless smoke test
```

## License

MIT — see [LICENSE](LICENSE).
