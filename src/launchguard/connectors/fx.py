"""Live foreign-exchange evidence with explicit provenance and fallback."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Dict, Optional, Tuple

import httpx

from launchguard.models import FxQuote

FALLBACK_RATES: Dict[Tuple[str, str], Decimal] = {
    ("EUR", "USD"): Decimal("1.08"),
    ("USD", "EUR"): Decimal("0.9259"),
    ("GBP", "USD"): Decimal("1.27"),
    ("USD", "GBP"): Decimal("0.7874"),
    ("CNY", "USD"): Decimal("0.1390"),
    ("USD", "CNY"): Decimal("7.1942"),
}


class FxClient:
    """Fetch reference rates from Frankfurter, which aggregates official sources."""

    def __init__(
        self,
        mode: str = "live",
        timeout_seconds: float = 8.0,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self.mode = mode
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    def quote(self, base: str, quote: str) -> FxQuote:
        base = base.upper()
        quote = quote.upper()
        if base == quote:
            return FxQuote(
                base=base,
                quote=quote,
                rate=Decimal("1"),
                as_of=date.today().isoformat(),
                provider="identity",
                source_url="local://identity-rate",
                mode="identity",
            )
        if self.mode == "offline":
            return self._fallback(base, quote, "offline mode")

        url = "https://api.frankfurter.app/latest"
        params = {"from": base, "to": quote}
        try:
            with httpx.Client(
                timeout=self.timeout_seconds,
                follow_redirects=True,
                transport=self.transport,
            ) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                payload = response.json()
            rate = Decimal(str(payload["rates"][quote]))
            return FxQuote(
                base=base,
                quote=quote,
                rate=rate,
                as_of=str(payload["date"]),
                provider="Frankfurter / official reference-rate providers",
                source_url=str(response.url),
                mode="live",
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            return self._fallback(base, quote, exc.__class__.__name__)

    def _fallback(self, base: str, quote: str, reason: str) -> FxQuote:
        rate = FALLBACK_RATES.get((base, quote))
        if rate is None:
            raise ValueError(
                f"No live or fallback FX rate is available for {base}/{quote}: {reason}"
            )
        return FxQuote(
            base=base,
            quote=quote,
            rate=rate,
            as_of="2026-01-02",
            provider=f"bundled fallback ({reason})",
            source_url="docs://fallback-fx-rates",
            mode="fallback",
        )
