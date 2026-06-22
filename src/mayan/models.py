"""Pydantic v2 models for Mayan Finance API responses.

Field names follow Python conventions (snake_case) while accepting the API's
camelCase payloads via ``populate_by_name`` + ``alias``. Every model tolerates
unknown fields (``extra="allow"``) so it keeps working as the API evolves and so
the many protocol-specific quote fields not modelled here remain accessible.

Token amounts straddle two conventions on Mayan: human-readable decimals (e.g.
``expected_amount_out``) and raw smallest-unit strings (the ``*_base_units`` /
``*64`` fields). Both are surfaced; addresses and raw amounts are kept as strings
so Solana, EVM and Sui values all round-trip without precision loss.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class _Model(BaseModel):
    """Base with camelCase aliasing and forward-compatible extra handling."""

    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow",
    )


class Token(_Model):
    """A token on one of Mayan's supported chains (Solana, EVM or Sui).

    The same token is addressed differently per ecosystem: ``mint`` carries the
    Solana SPL mint while ``contract`` carries the EVM/Sui contract address (for
    Solana tokens the two coincide). ``chain_id`` is Mayan's internal numeric id
    and ``w_chain_id`` the corresponding Wormhole chain id.
    """

    name: Optional[str] = Field(default=None, description="Human-readable token name.")
    symbol: str = Field(description="Ticker symbol, e.g. ``USDC``.")
    decimals: int = Field(description="Number of decimals used to scale raw amounts.")
    standard: Optional[str] = Field(
        default=None,
        description="Token standard: ``erc20``, ``native``, ``spl`` or ``spl2022``.",
    )
    mint: Optional[str] = Field(
        default=None, description="Solana SPL mint address (empty for non-Solana tokens)."
    )
    contract: Optional[str] = Field(
        default=None, description="EVM/Sui contract address (or the mint for Solana tokens)."
    )
    chain_id: Optional[int] = Field(
        default=None, alias="chainId", description="Mayan's internal numeric chain id."
    )
    w_chain_id: Optional[int] = Field(
        default=None, alias="wChainId", description="Wormhole chain id for this token's chain."
    )
    verified: Optional[bool] = Field(
        default=None, description="True when Mayan has verified the token."
    )
    logo_uri: Optional[str] = Field(
        default=None, alias="logoURI", description="URL of the token logo image."
    )
    coingecko_id: Optional[str] = Field(
        default=None, alias="coingeckoId", description="CoinGecko id for price lookups."
    )
    supports_permit: Optional[bool] = Field(
        default=None, alias="supportsPermit", description="True if the ERC-20 supports EIP-2612."
    )
    has_auction: Optional[bool] = Field(
        default=None, alias="hasAuction", description="True if the token routes via Swift auctions."
    )


class Quote(_Model):
    """A single cross-chain route returned inside a ``GET /v3/quote`` response.

    Mayan returns several candidate quotes (one per protocol it can route
    through); :attr:`type` identifies the protocol, e.g. ``MCTP``, ``SWIFT`` or
    ``WH`` (Wormhole). Amounts come in both human-readable (``expected_amount_out``)
    and raw smallest-unit (``expected_amount_out_base_units``) forms.

    Many additional protocol-specific fields are present on the wire and remain
    accessible via attribute access thanks to ``extra="allow"``.
    """

    type: str = Field(description="Routing protocol, e.g. ``MCTP``, ``SWIFT`` or ``WH``.")
    from_chain: str = Field(alias="fromChain", description="Source chain name, e.g. ``solana``.")
    to_chain: str = Field(alias="toChain", description="Destination chain name, e.g. ``ethereum``.")
    from_token: Optional[Token] = Field(
        default=None, alias="fromToken", description="Token being sold/sent."
    )
    to_token: Optional[Token] = Field(
        default=None, alias="toToken", description="Token to receive."
    )
    slippage_bps: Optional[int] = Field(
        default=None, alias="slippageBps", description="Applied slippage tolerance in basis points."
    )
    effective_amount_in: Optional[float] = Field(
        default=None, alias="effectiveAmountIn", description="Input amount actually routed (whole)."
    )
    effective_amount_in_base_units: Optional[str] = Field(
        default=None,
        alias="effectiveAmountIn64",
        description="Input amount routed, in the source token's smallest unit.",
    )
    expected_amount_out: Optional[float] = Field(
        default=None,
        alias="expectedAmountOut",
        description="Expected output amount in whole destination-token units.",
    )
    expected_amount_out_base_units: Optional[str] = Field(
        default=None,
        alias="expectedAmountOutBaseUnits",
        description="Expected output in the destination token's smallest unit.",
    )
    min_amount_out: Optional[float] = Field(
        default=None,
        alias="minAmountOut",
        description="Guaranteed minimum output after slippage (whole units).",
    )
    min_amount_out_base_units: Optional[str] = Field(
        default=None,
        alias="minAmountOutBaseUnits",
        description="Guaranteed minimum output in the destination token's smallest unit.",
    )
    min_received: Optional[float] = Field(
        default=None, alias="minReceived", description="Minimum the recipient receives (whole)."
    )
    min_received_base_units: Optional[str] = Field(
        default=None,
        alias="minReceivedBaseUnits",
        description="Minimum the recipient receives, in smallest units.",
    )
    price: Optional[float] = Field(
        default=None, description="Indicative price of the source token in destination-token terms."
    )
    eta: Optional[int] = Field(
        default=None, description="Estimated time to completion, in minutes."
    )
    eta_seconds: Optional[int] = Field(
        default=None, alias="etaSeconds", description="Estimated time to completion, in seconds."
    )
    client_eta: Optional[str] = Field(
        default=None, alias="clientEta", description="Human-readable ETA, e.g. ``1 min``."
    )
    gas_drop: Optional[float] = Field(
        default=None,
        alias="gasDrop",
        description="Native gas dropped to the recipient on the destination chain.",
    )
    referrer_bps: Optional[int] = Field(
        default=None, alias="referrerBps", description="Referrer fee in basis points."
    )
    gasless: Optional[bool] = Field(
        default=None, description="True when the route can be executed gaslessly."
    )
    has_auction: Optional[bool] = Field(
        default=None, alias="hasAuction", description="True when the route uses a Swift auction."
    )
    deadline_base_units: Optional[str] = Field(
        default=None, alias="deadline64", description="Quote deadline as a unix timestamp string."
    )


class QuoteResponse(_Model):
    """The full body of ``GET /v3/quote``: the candidate quotes plus metadata."""

    quotes: list[Quote] = Field(
        default_factory=list, description="Candidate routes, one per available protocol."
    )
    minimum_sdk_version: Optional[str] = Field(
        default=None,
        alias="minimumSdkVersion",
        description="Lowest SDK/client version the API will still serve.",
    )


class SwapStatus(_Model):
    """A swap/order as returned by the explorer API (``GET /v3/swap/trx/{hash}``).

    :attr:`status` is the fine-grained protocol state (e.g.
    ``INITIATED_ON_EVM_MCTP``, ``REDEEMED_ON_EVM_WITH_FEE``, ``ORDER_SETTLED``),
    while :attr:`client_status` is the coarse lifecycle state used for polling:
    ``INPROGRESS``, ``COMPLETED`` or ``REFUNDED``. Prefer the :attr:`is_completed`,
    :attr:`is_refunded` and :attr:`is_terminal` helpers over comparing strings.

    The on-the-wire object carries dozens of protocol-specific fields; the ones
    not modelled here remain accessible via attribute access (``extra="allow"``).
    """

    id: Optional[str] = Field(default=None, description="Mayan's internal swap id (UUID).")
    trader: Optional[str] = Field(default=None, description="Address that initiated the swap.")
    source_tx_hash: Optional[str] = Field(
        default=None, alias="sourceTxHash", description="Source-chain transaction hash."
    )
    source_chain: Optional[str] = Field(
        default=None, alias="sourceChain", description="Source chain id (as a string)."
    )
    dest_chain: Optional[str] = Field(
        default=None, alias="destChain", description="Destination chain id (as a string)."
    )
    status: Optional[str] = Field(
        default=None, description="Fine-grained protocol state, e.g. ``REDEEMED_ON_EVM_WITH_FEE``."
    )
    client_status: Optional[str] = Field(
        default=None,
        alias="clientStatus",
        description="Coarse lifecycle state: ``INPROGRESS``, ``COMPLETED`` or ``REFUNDED``.",
    )
    service: Optional[str] = Field(
        default=None, description="Protocol/service handling the swap, e.g. ``MCTP_FAST_BRIDGE``."
    )
    from_amount: Optional[str] = Field(
        default=None, alias="fromAmount", description="Input amount (whole units, as a string)."
    )
    to_amount: Optional[str] = Field(
        default=None, alias="toAmount", description="Output amount (whole units, as a string)."
    )
    from_token_symbol: Optional[str] = Field(
        default=None, alias="fromTokenSymbol", description="Source token symbol."
    )
    to_token_symbol: Optional[str] = Field(
        default=None, alias="toTokenSymbol", description="Destination token symbol."
    )
    order_hash: Optional[str] = Field(
        default=None, alias="orderHash", description="Swift order hash, when applicable."
    )
    fulfill_tx_hash: Optional[str] = Field(
        default=None, alias="fulfillTxHash", description="Destination-chain fulfillment tx hash."
    )

    @property
    def is_completed(self) -> bool:
        """True when the swap completed successfully (``clientStatus == COMPLETED``)."""
        return self.client_status == "COMPLETED"

    @property
    def is_refunded(self) -> bool:
        """True when the swap was refunded (``clientStatus == REFUNDED``)."""
        return self.client_status == "REFUNDED"

    @property
    def is_terminal(self) -> bool:
        """True once the swap reached a final state (completed or refunded)."""
        return self.is_completed or self.is_refunded
