"""Live smoke tests against the real Mayan Finance API.

Deselected by default (``addopts = -m 'not integration'``). Run explicitly with:

    pytest -m integration

These hit keyless public endpoints; no API key required.
"""

from __future__ import annotations

import pytest

from mayan import MayanClient

pytestmark = pytest.mark.integration


def test_live_tokens_solana() -> None:
    with MayanClient() as client:
        tokens = client.get_tokens(chain="solana")
    assert "solana" in tokens
    assert len(tokens["solana"]) > 0
    # native SOL is always present
    assert any(t.symbol == "SOL" for t in tokens["solana"])
