"""Synchronous and asynchronous clients for the Mayan Finance API.

Mayan splits its surface across two hosts: the *price API*
(``price-api.mayan.finance``) serves quotes and token lists, while the
*explorer API* (``explorer-api.mayan.finance``) serves swap/order status. A
single client talks to both: ``base_url`` configures the former and
``status_base_url`` the latter.
"""

from __future__ import annotations

import asyncio
import warnings
from types import TracebackType
from typing import Any, Optional

import httpx

from . import _transport as _t
from ._transport import (
    DEFAULT_BASE_URL,
    DEFAULT_STATUS_BASE_URL,
    RateLimit,
    RateLimitState,
    backoff_seconds,
    build_query,
    parse_response,
)
from .exceptions import MayanAPIError
from .models import Quote, QuoteResponse, SwapStatus, Token

DEFAULT_API_KEY_HEADER = "x-api-key"
DEFAULT_REFERER = "mayan-py"
DEFAULT_SDK_VERSION = "10_0_0"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 3


def _build_headers(api_key: Optional[str], api_key_header: str, referer: str) -> dict[str, str]:
    # Mayan's quote endpoint requires a ``referer`` header; send it on every
    # request so the price API accepts the call.
    headers = {"Accept": "application/json", "referer": referer}
    if api_key:
        headers[api_key_header] = api_key
    return headers


def _normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def _warn_ignored_args_for_injected_client(
    *,
    base_url: str,
    api_key: Optional[str],
    api_key_header: str,
) -> None:
    """Warn that base_url/auth are ignored when an http_client is injected.

    An injected client is an escape hatch: it owns its own ``base_url`` and
    headers, so any conflicting constructor args are silently dropped. Surface
    that instead of letting requests mysteriously hit the wrong host.
    """
    ignored = []
    if base_url != DEFAULT_BASE_URL:
        ignored.append("base_url")
    if api_key is not None:
        ignored.append("api_key")
    if api_key_header != DEFAULT_API_KEY_HEADER:
        ignored.append("api_key_header")
    if ignored:
        warnings.warn(
            "An explicit http_client was provided; "
            f"{', '.join(ignored)} {'is' if len(ignored) == 1 else 'are'} ignored. "
            "Configure base_url and auth headers on the injected client instead.",
            UserWarning,
            stacklevel=3,
        )


def _quote_query(
    *,
    amount: Optional[str],
    amount_base_units: Optional[str],
    from_token: str,
    from_chain: str,
    to_token: str,
    to_chain: str,
    slippage_bps: Any,
    sdk_version: str,
    referrer: Optional[str],
    referrer_bps: Optional[int],
    gas_drop: Optional[float],
    destination_address: Optional[str],
    swift: bool,
    mctp: bool,
    wormhole: bool,
    fast_mctp: bool,
    gasless: bool,
    shuttle: bool,
    extra_params: Optional[dict[str, Any]],
) -> dict[str, str]:
    """Build the ``GET /v3/quote`` query string.

    Exactly one of ``amount`` (whole units) or ``amount_base_units`` (raw
    smallest units) must be set by the caller. Protocol flags are sent as the
    lowercase ``"true"``/``"false"`` strings the API expects; they are enabled by
    default because the API returns ``406 ROUTE_NOT_FOUND`` when none are on.
    """

    def flag(value: bool) -> str:
        return "true" if value else "false"

    params = build_query(
        amountIn=amount,
        amountIn64=amount_base_units,
        fromToken=from_token,
        fromChain=from_chain,
        toToken=to_token,
        toChain=to_chain,
        slippageBps=slippage_bps,
        sdkVersion=sdk_version,
        referrer=referrer,
        referrerBps=referrer_bps,
        gasDrop=gas_drop,
        destinationAddress=destination_address,
        swift=flag(swift),
        mctp=flag(mctp),
        wormhole=flag(wormhole),
        fastMctp=flag(fast_mctp),
        gasless=flag(gasless),
        shuttle=flag(shuttle),
    )
    if extra_params:
        params.update({k: str(v) for k, v in extra_params.items() if v is not None})
    return params


def _resolve_amount(amount: Optional[str], amount_base_units: Optional[str]) -> None:
    if amount is None and amount_base_units is None:
        raise ValueError("provide either amount (whole units) or amount_base_units (raw units)")


def _best_quote(resp: QuoteResponse) -> Quote:
    if not resp.quotes:
        raise MayanAPIError(
            "No route found for the requested swap", status_code=406, response_body=None
        )
    return resp.quotes[0]


def _parse_tokens(payload: Any) -> dict[str, list[Token]]:
    if not isinstance(payload, dict):
        return {}
    return {
        chain: [Token.model_validate(t) for t in token_list]
        for chain, token_list in payload.items()
    }


def _parse_swaps(payload: Any) -> list[SwapStatus]:
    data = payload.get("data", []) if isinstance(payload, dict) else []
    return [SwapStatus.model_validate(s) for s in data]


class MayanClient:
    """Synchronous client for the Mayan Finance API.

    All endpoints used here are public and keyless; an API key is optional. The
    client tracks any ``ratelimit-*`` response headers, pauses proactively when
    the quota is exhausted, and retries 429s with backoff.

    Example:
        >>> with MayanClient() as client:  # doctest: +SKIP
        ...     quote = client.get_quote(
        ...         amount="100",
        ...         from_token="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC (Solana)
        ...         from_chain="solana",
        ...         to_token="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",  # USDC (Ethereum)
        ...         to_chain="ethereum",
        ...     )
        ...     quote.expected_amount_out
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        status_base_url: str = DEFAULT_STATUS_BASE_URL,
        api_key_header: str = DEFAULT_API_KEY_HEADER,
        referer: str = DEFAULT_REFERER,
        sdk_version: str = DEFAULT_SDK_VERSION,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        """Create a client.

        Args:
            api_key: Optional Mayan API key. All endpoints work without one.
            base_url: Price API base URL (quotes/tokens). Override for a proxy.
            status_base_url: Explorer API base URL (swap status).
            api_key_header: Header name used to send ``api_key``.
            referer: Value sent in the required ``referer`` header on every
                request; set this to identify your integration.
            sdk_version: ``sdkVersion`` sent with quote/token requests; the API
                requires it to serve a valid response.
            timeout: Per-request timeout in seconds.
            max_retries: Maximum number of 429 retries before raising
                :class:`~mayan.exceptions.MayanRateLimitError`.
            http_client: An existing ``httpx.Client`` to reuse. When provided it
                is used as-is for both hosts and conflicting ``base_url``/
                ``api_key``/``api_key_header`` are ignored (with a warning).
        """
        self.max_retries = max_retries
        self.sdk_version = sdk_version
        self.status_base_url = _normalize_base_url(status_base_url)
        self._rate = RateLimitState()
        if http_client is not None:
            _warn_ignored_args_for_injected_client(
                base_url=base_url, api_key=api_key, api_key_header=api_key_header
            )
            self._http = http_client
            self.base_url = _normalize_base_url(str(http_client.base_url))
        else:
            self.base_url = _normalize_base_url(base_url)
            self._http = httpx.Client(
                base_url=self.base_url,
                headers=_build_headers(api_key, api_key_header, referer),
                timeout=timeout,
            )

    @property
    def rate_limit(self) -> Optional[RateLimit]:
        """The most recent rate-limit snapshot, or ``None`` before any call."""
        if self._rate.current.limit is None and self._rate.current.remaining is None:
            return None
        return self._rate.current

    def __enter__(self) -> MayanClient:
        """Enter a context manager; returns ``self``."""
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        """Exit the context manager, closing the underlying HTTP client."""
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP client and release its connections."""
        self._http.close()

    def _request(self, method: str, url: str, **kwargs: Any) -> Any:
        wait = self._rate.proactive_wait()
        if wait > 0:
            _t.time.sleep(wait)

        attempt = 0
        while True:
            response = self._http.request(method, url, **kwargs)
            self._rate.update(response.headers)
            if response.status_code == 429 and attempt < self.max_retries:
                _t.time.sleep(backoff_seconds(attempt, response))
                attempt += 1
                continue
            return parse_response(response)

    # -- Endpoints -----------------------------------------------------------

    def get_quotes(
        self,
        *,
        from_token: str,
        from_chain: str,
        to_token: str,
        to_chain: str,
        amount: Optional[str] = None,
        amount_base_units: Optional[str] = None,
        slippage_bps: Any = "auto",
        referrer: Optional[str] = None,
        referrer_bps: Optional[int] = None,
        gas_drop: Optional[float] = None,
        destination_address: Optional[str] = None,
        swift: bool = True,
        mctp: bool = True,
        wormhole: bool = True,
        fast_mctp: bool = True,
        gasless: bool = False,
        shuttle: bool = False,
        extra_params: Optional[dict[str, Any]] = None,
    ) -> QuoteResponse:
        """Fetch every candidate cross-chain route (``GET /v3/quote``).

        Returns all quotes Mayan can offer (one per enabled protocol) plus the
        minimum SDK version. Use :meth:`get_quote` for just the best one.

        Args:
            from_token: Source token address (SPL mint on Solana, contract on
                EVM/Sui; the zero address denotes native).
            from_chain: Source chain name, e.g. ``solana`` or ``ethereum``.
            to_token: Destination token address.
            to_chain: Destination chain name.
            amount: Amount to send in whole token units (e.g. ``"100"`` for 100
                USDC). Mutually exclusive with ``amount_base_units``.
            amount_base_units: Amount to send in the source token's smallest unit
                (e.g. ``"100000000"``). Mutually exclusive with ``amount``.
            slippage_bps: Slippage tolerance in basis points, or ``"auto"`` to
                let Mayan choose. Defaults to ``"auto"``.
            referrer: Referrer address credited with ``referrer_bps`` fees.
            referrer_bps: Referrer fee in basis points.
            gas_drop: Native gas to drop to the recipient on the destination
                chain, in whole units.
            destination_address: Recipient address (defaults to the sender on the
                executing side).
            swift: Enable Swift (auction) routes.
            mctp: Enable MCTP (Circle CCTP) routes.
            wormhole: Enable Wormhole routes.
            fast_mctp: Enable fast-MCTP routes.
            gasless: Enable gasless routes.
            shuttle: Enable Shuttle routes.
            extra_params: Additional raw query params to merge in (escape hatch
                for newer flags not yet modelled).

        Returns:
            A :class:`~mayan.QuoteResponse` with the candidate quotes.

        Raises:
            ValueError: Neither ``amount`` nor ``amount_base_units`` was given.
            MayanAPIError: The API rejected the request (e.g. 406 no route).
            MayanRateLimitError: Rate limited after exhausting retries.
        """
        _resolve_amount(amount, amount_base_units)
        params = _quote_query(
            amount=amount,
            amount_base_units=amount_base_units,
            from_token=from_token,
            from_chain=from_chain,
            to_token=to_token,
            to_chain=to_chain,
            slippage_bps=slippage_bps,
            sdk_version=self.sdk_version,
            referrer=referrer,
            referrer_bps=referrer_bps,
            gas_drop=gas_drop,
            destination_address=destination_address,
            swift=swift,
            mctp=mctp,
            wormhole=wormhole,
            fast_mctp=fast_mctp,
            gasless=gasless,
            shuttle=shuttle,
            extra_params=extra_params,
        )
        return QuoteResponse.model_validate(self._request("GET", "/v3/quote", params=params))

    def get_quote(
        self,
        *,
        from_token: str,
        from_chain: str,
        to_token: str,
        to_chain: str,
        amount: Optional[str] = None,
        amount_base_units: Optional[str] = None,
        slippage_bps: Any = "auto",
        referrer: Optional[str] = None,
        referrer_bps: Optional[int] = None,
        gas_drop: Optional[float] = None,
        destination_address: Optional[str] = None,
        swift: bool = True,
        mctp: bool = True,
        wormhole: bool = True,
        fast_mctp: bool = True,
        gasless: bool = False,
        shuttle: bool = False,
        extra_params: Optional[dict[str, Any]] = None,
    ) -> Quote:
        """Get the single best cross-chain quote (the headline call).

        Convenience wrapper over :meth:`get_quotes` that returns the first
        (best) candidate. See :meth:`get_quotes` for the full argument reference.

        Returns:
            The best :class:`~mayan.Quote`.

        Raises:
            ValueError: Neither ``amount`` nor ``amount_base_units`` was given.
            MayanAPIError: The API rejected the request, or no route was found.
            MayanRateLimitError: Rate limited after exhausting retries.
        """
        return _best_quote(
            self.get_quotes(
                from_token=from_token,
                from_chain=from_chain,
                to_token=to_token,
                to_chain=to_chain,
                amount=amount,
                amount_base_units=amount_base_units,
                slippage_bps=slippage_bps,
                referrer=referrer,
                referrer_bps=referrer_bps,
                gas_drop=gas_drop,
                destination_address=destination_address,
                swift=swift,
                mctp=mctp,
                wormhole=wormhole,
                fast_mctp=fast_mctp,
                gasless=gasless,
                shuttle=shuttle,
                extra_params=extra_params,
            )
        )

    def get_tokens(
        self,
        *,
        chain: Optional[str] = None,
        standard: Optional[str] = None,
        non_portal: Optional[bool] = None,
    ) -> dict[str, list[Token]]:
        """Fetch the supported-token catalog (``GET /v3/tokens``).

        Args:
            chain: Restrict to one chain by name (e.g. ``solana``). When omitted,
                tokens for all supported chains are returned.
            standard: Restrict to a token standard (``erc20``, ``native``,
                ``spl`` or ``spl2022``).
            non_portal: When ``True``, exclude Portal (Wormhole-wrapped) tokens.

        Returns:
            A mapping of chain name to the list of :class:`~mayan.Token` objects
            supported on that chain.

        Raises:
            MayanAPIError: The request failed.
            MayanRateLimitError: Rate limited after exhausting retries.
        """
        params = build_query(
            chain=chain,
            standard=standard,
            nonPortal=non_portal,
            sdkVersion=self.sdk_version,
        )
        return _parse_tokens(self._request("GET", "/v3/tokens", params=params))

    def get_swap_status(self, *, tx_hash: str) -> SwapStatus:
        """Look up a swap/order by its source transaction hash.

        Hits the explorer API (``GET /v3/swap/trx/{tx_hash}``).

        Args:
            tx_hash: The source-chain transaction hash that initiated the swap.

        Returns:
            A :class:`~mayan.SwapStatus` describing the swap's current state.

        Raises:
            MayanAPIError: The lookup failed (e.g. unknown hash).
            MayanRateLimitError: Rate limited after exhausting retries.
        """
        url = f"{self.status_base_url}/v3/swap/trx/{tx_hash}"
        return SwapStatus.model_validate(self._request("GET", url))

    def list_swaps(
        self,
        *,
        trader: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> list[SwapStatus]:
        """List swaps from the explorer API (``GET /v3/swaps``).

        Args:
            trader: Filter to swaps initiated by this address.
            limit: Maximum number of swaps to return.
            offset: Number of swaps to skip (for pagination).

        Returns:
            The matching :class:`~mayan.SwapStatus` objects.

        Raises:
            MayanAPIError: The request failed.
            MayanRateLimitError: Rate limited after exhausting retries.
        """
        url = f"{self.status_base_url}/v3/swaps"
        params = build_query(trader=trader, limit=limit, offset=offset)
        return _parse_swaps(self._request("GET", url, params=params))

    def poll_swap_status(
        self,
        *,
        tx_hash: str,
        interval: float = 5.0,
        timeout: float = 300.0,
        max_interval: float = 30.0,
    ) -> SwapStatus:
        """Poll a swap's status until it is terminal (completed or refunded).

        Repeatedly calls :meth:`get_swap_status`, sleeping between attempts with
        the delay doubling from ``interval`` up to ``max_interval``.

        Args:
            tx_hash: The source-chain transaction hash to track.
            interval: Initial delay between polls, in seconds.
            timeout: Maximum total time to wait, in seconds.
            max_interval: Cap on the (exponentially growing) poll delay.

        Returns:
            The terminal :class:`~mayan.SwapStatus` (completed or refunded).

        Raises:
            TimeoutError: No terminal state was reached within ``timeout``.
            MayanAPIError: A status request failed.
            MayanRateLimitError: Rate limited after exhausting retries.
        """
        elapsed = 0.0
        delay = interval
        while True:
            status = self.get_swap_status(tx_hash=tx_hash)
            if status.is_terminal:
                return status
            if elapsed >= timeout:
                raise TimeoutError(
                    f"swap {tx_hash} not terminal after {timeout}s "
                    f"(last clientStatus: {status.client_status})"
                )
            _t.time.sleep(delay)
            elapsed += delay
            delay = min(delay * 2, max_interval)


class AsyncMayanClient:
    """Asynchronous client for the Mayan Finance API.

    A coroutine-based mirror of :class:`MayanClient` with identical endpoints,
    parameters and return types. Use it as an async context manager so the
    underlying HTTP connections are closed on exit.

    Example:
        >>> import asyncio
        >>> async def main():
        ...     async with AsyncMayanClient() as client:
        ...         return await client.get_tokens(chain="solana")
        >>> tokens = asyncio.run(main())  # doctest: +SKIP
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        status_base_url: str = DEFAULT_STATUS_BASE_URL,
        api_key_header: str = DEFAULT_API_KEY_HEADER,
        referer: str = DEFAULT_REFERER,
        sdk_version: str = DEFAULT_SDK_VERSION,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        """Create an async client.

        Args:
            api_key: Optional Mayan API key. All endpoints work without one.
            base_url: Price API base URL (quotes/tokens). Override for a proxy.
            status_base_url: Explorer API base URL (swap status).
            api_key_header: Header name used to send ``api_key``.
            referer: Value sent in the required ``referer`` header on every
                request; set this to identify your integration.
            sdk_version: ``sdkVersion`` sent with quote/token requests.
            timeout: Per-request timeout in seconds.
            max_retries: Maximum number of 429 retries before raising
                :class:`~mayan.exceptions.MayanRateLimitError`.
            http_client: An existing ``httpx.AsyncClient`` to reuse. When provided
                it is used as-is and conflicting ``base_url``/``api_key``/
                ``api_key_header`` are ignored (with a warning).
        """
        self.max_retries = max_retries
        self.sdk_version = sdk_version
        self.status_base_url = _normalize_base_url(status_base_url)
        self._rate = RateLimitState()
        if http_client is not None:
            _warn_ignored_args_for_injected_client(
                base_url=base_url, api_key=api_key, api_key_header=api_key_header
            )
            self._http = http_client
            self.base_url = _normalize_base_url(str(http_client.base_url))
        else:
            self.base_url = _normalize_base_url(base_url)
            self._http = httpx.AsyncClient(
                base_url=self.base_url,
                headers=_build_headers(api_key, api_key_header, referer),
                timeout=timeout,
            )

    @property
    def rate_limit(self) -> Optional[RateLimit]:
        """The most recent rate-limit snapshot, or ``None`` before any call."""
        if self._rate.current.limit is None and self._rate.current.remaining is None:
            return None
        return self._rate.current

    async def __aenter__(self) -> AsyncMayanClient:
        """Enter the async context manager; returns ``self``."""
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        """Exit the async context manager, closing the HTTP client."""
        await self.close()

    async def close(self) -> None:
        """Close the underlying async HTTP client and release its connections."""
        await self._http.aclose()

    async def _request(self, method: str, url: str, **kwargs: Any) -> Any:
        wait = self._rate.proactive_wait()
        if wait > 0:
            await asyncio.sleep(wait)

        attempt = 0
        while True:
            response = await self._http.request(method, url, **kwargs)
            self._rate.update(response.headers)
            if response.status_code == 429 and attempt < self.max_retries:
                await asyncio.sleep(backoff_seconds(attempt, response))
                attempt += 1
                continue
            return parse_response(response)

    async def get_quotes(
        self,
        *,
        from_token: str,
        from_chain: str,
        to_token: str,
        to_chain: str,
        amount: Optional[str] = None,
        amount_base_units: Optional[str] = None,
        slippage_bps: Any = "auto",
        referrer: Optional[str] = None,
        referrer_bps: Optional[int] = None,
        gas_drop: Optional[float] = None,
        destination_address: Optional[str] = None,
        swift: bool = True,
        mctp: bool = True,
        wormhole: bool = True,
        fast_mctp: bool = True,
        gasless: bool = False,
        shuttle: bool = False,
        extra_params: Optional[dict[str, Any]] = None,
    ) -> QuoteResponse:
        """Fetch every candidate cross-chain route (``GET /v3/quote``).

        Async counterpart of :meth:`MayanClient.get_quotes`; see it for the full
        argument reference.

        Returns:
            A :class:`~mayan.QuoteResponse` with the candidate quotes.

        Raises:
            ValueError: Neither ``amount`` nor ``amount_base_units`` was given.
            MayanAPIError: The API rejected the request.
            MayanRateLimitError: Rate limited after exhausting retries.
        """
        _resolve_amount(amount, amount_base_units)
        params = _quote_query(
            amount=amount,
            amount_base_units=amount_base_units,
            from_token=from_token,
            from_chain=from_chain,
            to_token=to_token,
            to_chain=to_chain,
            slippage_bps=slippage_bps,
            sdk_version=self.sdk_version,
            referrer=referrer,
            referrer_bps=referrer_bps,
            gas_drop=gas_drop,
            destination_address=destination_address,
            swift=swift,
            mctp=mctp,
            wormhole=wormhole,
            fast_mctp=fast_mctp,
            gasless=gasless,
            shuttle=shuttle,
            extra_params=extra_params,
        )
        payload = await self._request("GET", "/v3/quote", params=params)
        return QuoteResponse.model_validate(payload)

    async def get_quote(
        self,
        *,
        from_token: str,
        from_chain: str,
        to_token: str,
        to_chain: str,
        amount: Optional[str] = None,
        amount_base_units: Optional[str] = None,
        slippage_bps: Any = "auto",
        referrer: Optional[str] = None,
        referrer_bps: Optional[int] = None,
        gas_drop: Optional[float] = None,
        destination_address: Optional[str] = None,
        swift: bool = True,
        mctp: bool = True,
        wormhole: bool = True,
        fast_mctp: bool = True,
        gasless: bool = False,
        shuttle: bool = False,
        extra_params: Optional[dict[str, Any]] = None,
    ) -> Quote:
        """Get the single best cross-chain quote (the headline call).

        Async counterpart of :meth:`MayanClient.get_quote`.

        Returns:
            The best :class:`~mayan.Quote`.

        Raises:
            ValueError: Neither ``amount`` nor ``amount_base_units`` was given.
            MayanAPIError: The API rejected the request, or no route was found.
            MayanRateLimitError: Rate limited after exhausting retries.
        """
        return _best_quote(
            await self.get_quotes(
                from_token=from_token,
                from_chain=from_chain,
                to_token=to_token,
                to_chain=to_chain,
                amount=amount,
                amount_base_units=amount_base_units,
                slippage_bps=slippage_bps,
                referrer=referrer,
                referrer_bps=referrer_bps,
                gas_drop=gas_drop,
                destination_address=destination_address,
                swift=swift,
                mctp=mctp,
                wormhole=wormhole,
                fast_mctp=fast_mctp,
                gasless=gasless,
                shuttle=shuttle,
                extra_params=extra_params,
            )
        )

    async def get_tokens(
        self,
        *,
        chain: Optional[str] = None,
        standard: Optional[str] = None,
        non_portal: Optional[bool] = None,
    ) -> dict[str, list[Token]]:
        """Fetch the supported-token catalog (``GET /v3/tokens``).

        Async counterpart of :meth:`MayanClient.get_tokens`.

        Returns:
            A mapping of chain name to the list of :class:`~mayan.Token` objects.

        Raises:
            MayanAPIError: The request failed.
            MayanRateLimitError: Rate limited after exhausting retries.
        """
        params = build_query(
            chain=chain,
            standard=standard,
            nonPortal=non_portal,
            sdkVersion=self.sdk_version,
        )
        return _parse_tokens(await self._request("GET", "/v3/tokens", params=params))

    async def get_swap_status(self, *, tx_hash: str) -> SwapStatus:
        """Look up a swap/order by its source transaction hash.

        Async counterpart of :meth:`MayanClient.get_swap_status`.

        Returns:
            A :class:`~mayan.SwapStatus` describing the swap's current state.

        Raises:
            MayanAPIError: The lookup failed.
            MayanRateLimitError: Rate limited after exhausting retries.
        """
        url = f"{self.status_base_url}/v3/swap/trx/{tx_hash}"
        return SwapStatus.model_validate(await self._request("GET", url))

    async def list_swaps(
        self,
        *,
        trader: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> list[SwapStatus]:
        """List swaps from the explorer API (``GET /v3/swaps``).

        Async counterpart of :meth:`MayanClient.list_swaps`.

        Returns:
            The matching :class:`~mayan.SwapStatus` objects.

        Raises:
            MayanAPIError: The request failed.
            MayanRateLimitError: Rate limited after exhausting retries.
        """
        url = f"{self.status_base_url}/v3/swaps"
        params = build_query(trader=trader, limit=limit, offset=offset)
        return _parse_swaps(await self._request("GET", url, params=params))

    async def poll_swap_status(
        self,
        *,
        tx_hash: str,
        interval: float = 5.0,
        timeout: float = 300.0,
        max_interval: float = 30.0,
    ) -> SwapStatus:
        """Poll a swap's status until it is terminal (completed or refunded).

        Async counterpart of :meth:`MayanClient.poll_swap_status`. Awaits between
        polls so it does not block the event loop.

        Returns:
            The terminal :class:`~mayan.SwapStatus` (completed or refunded).

        Raises:
            TimeoutError: No terminal state was reached within ``timeout``.
            MayanAPIError: A status request failed.
            MayanRateLimitError: Rate limited after exhausting retries.
        """
        elapsed = 0.0
        delay = interval
        while True:
            status = await self.get_swap_status(tx_hash=tx_hash)
            if status.is_terminal:
                return status
            if elapsed >= timeout:
                raise TimeoutError(
                    f"swap {tx_hash} not terminal after {timeout}s "
                    f"(last clientStatus: {status.client_status})"
                )
            await asyncio.sleep(delay)
            elapsed += delay
            delay = min(delay * 2, max_interval)
