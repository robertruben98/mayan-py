"""Exception hierarchy for the Mayan Finance client."""

from __future__ import annotations

from typing import Any, Optional


class MayanError(Exception):
    """Base class for all errors raised by this library.

    Catch this to handle any mayan-py-originated failure regardless of kind. Note
    that low-level transport failures (timeouts, connection errors) propagate as
    the underlying :class:`httpx.HTTPError` subclasses, not as ``MayanError``.
    """


class MayanAPIError(MayanError):
    """The API returned a non-2xx response (other than rate limiting).

    A common case is HTTP 406 with ``{"code": "ROUTE_NOT_FOUND"}`` when no route
    exists for the requested swap; inspect :attr:`response_body` for the API's
    structured error.

    Attributes:
        status_code: The HTTP status code returned by the API.
        response_body: The parsed JSON response body, or ``None`` if the body
            was empty or not valid JSON.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        response_body: Optional[Any] = None,
    ) -> None:
        """Initialize the error.

        Args:
            message: Human-readable error message (the API's ``message``/``msg``
                field when available, otherwise a generated description).
            status_code: The HTTP status code returned by the API.
            response_body: The parsed JSON response body, if any.
        """
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class MayanRateLimitError(MayanAPIError):
    """HTTP 429: rate limit exceeded.

    Raised once the client's retries are exhausted (see ``max_retries``). The
    client retries 429s automatically before surfacing this.

    Attributes:
        retry_after: Seconds to wait before retrying, derived from the
            ``ratelimit-reset`` or ``retry-after`` response header, or ``None``
            if neither was present.
        status_code: Always ``429``.
        response_body: The parsed JSON response body, if any.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 429,
        retry_after: Optional[float] = None,
        response_body: Optional[Any] = None,
    ) -> None:
        """Initialize the error.

        Args:
            message: Human-readable error message.
            status_code: The HTTP status code (defaults to ``429``).
            retry_after: Seconds to wait before retrying, if the API advertised
                a reset window.
            response_body: The parsed JSON response body, if any.
        """
        super().__init__(message, status_code=status_code, response_body=response_body)
        self.retry_after = retry_after
