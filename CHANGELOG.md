# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-06-22

### Added
- Initial release: a typed Python client for the Mayan Finance API (cross-chain
  swaps and bridging across Solana, EVM chains and Sui).
- Synchronous `MayanClient` and asynchronous `AsyncMayanClient` over `httpx`.
- Pydantic v2 response models (`Quote`, `QuoteResponse`, `Token`, `SwapStatus`)
  with full type hints and `Field(description=...)`; `py.typed` packaged. Models
  use `extra="allow"` so the many protocol-specific fields stay accessible.
- Endpoints: `get_quote` / `get_quotes` (`GET /v3/quote`), `get_tokens`
  (`GET /v3/tokens`), `get_swap_status` (`GET /v3/swap/trx/{hash}`) and
  `list_swaps` (`GET /v3/swaps`) on the explorer API.
- `poll_swap_status()` helper that polls a swap until it is terminal
  (`COMPLETED` / `REFUNDED`) with exponential backoff, plus `SwapStatus`
  `is_completed` / `is_refunded` / `is_terminal` helpers.
- Quote protocol flags (`swift`, `mctp`, `wormhole`, `fast_mctp`, `gasless`,
  `shuttle`) enabled sensibly by default, since the API returns
  `406 ROUTE_NOT_FOUND` when none are on.
- Two configurable hosts (`base_url` price API, `status_base_url` explorer API),
  required `referer` header, `sdk_version`, optional `api_key`, and rate-limit
  awareness (reads `ratelimit-*` headers, retries `429`s with backoff).
- Rich Google-style docstrings, `examples/`, README quickstart and status badges.
- `QuoteResponse.minimum_sdk_version` normalizes the API's array form
  (`[7, 0, 0]`) into a dotted version string, so `get_quote`/`get_quotes` parse
  real production responses; covered by a live integration test.

[0.1.0]: https://github.com/robertruben98/mayan-py/releases/tag/v0.1.0
