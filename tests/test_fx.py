from decimal import Decimal

import httpx
import pytest

from launchguard.connectors.fx import FxClient


def test_identity_quote_is_exact() -> None:
    quote = FxClient(mode="live").quote("USD", "USD")
    assert quote.rate == Decimal("1")
    assert quote.mode == "identity"


def test_offline_quote_is_explicit_fallback() -> None:
    quote = FxClient(mode="offline").quote("EUR", "USD")
    assert quote.rate == Decimal("1.08")
    assert quote.mode == "fallback"
    assert "offline mode" in quote.provider


def test_live_quote_records_provenance() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"amount": 1, "base": "EUR", "date": "2026-10-06", "rates": {"USD": 1.17}},
            request=request,
        )

    quote = FxClient(transport=httpx.MockTransport(handler)).quote("EUR", "USD")
    assert quote.rate == Decimal("1.17")
    assert quote.mode == "live"
    assert "from=EUR" in quote.source_url


def test_live_failure_falls_back_and_unknown_pair_fails() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    client = FxClient(transport=httpx.MockTransport(handler))
    assert client.quote("GBP", "USD").mode == "fallback"
    with pytest.raises(ValueError, match="No live or fallback"):
        client.quote("AUD", "CAD")
