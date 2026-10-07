from decimal import Decimal

import pytest

from launchguard.models import FxQuote
from launchguard.services.pricing import PricingEngine


def identity_quote() -> FxQuote:
    return FxQuote(
        base="USD",
        quote="USD",
        rate=Decimal("1"),
        as_of="2026-10-07",
        provider="identity",
        source_url="local://identity-rate",
        mode="identity",
    )


def test_pricing_exposes_floor_and_four_stress_scenarios(sku) -> None:
    result = PricingEngine().price(sku, identity_quote())
    assert result.recommended_price >= result.minimum_price
    assert result.recommended_price.as_tuple().exponent == -2
    assert len(result.scenarios) == 4
    assert {item.name for item in result.scenarios} == {
        "base",
        "fx_stress_3pct",
        "returns_stress_2pp",
        "platform_fee_stress_1pp",
    }
    assert result.cost_breakdown.fixed_cost == Decimal("14.50")


def test_pricing_flags_competitor_gap_without_hiding_floor(sku) -> None:
    expensive = sku.model_copy(update={"competitor_price": Decimal("15")})
    result = PricingEngine().price(expensive, identity_quote())
    assert result.commercially_feasible is False
    assert any("above" in line for line in result.rationale)


def test_pricing_rejects_impossible_margin_stack(sku) -> None:
    impossible = sku.model_copy(
        update={
            "platform_fee_rate": Decimal("0.30"),
            "return_reserve_rate": Decimal("0.20"),
            "ad_cost_rate": Decimal("0.20"),
            "target_margin": Decimal("0.30"),
        }
    )
    with pytest.raises(ValueError, match="infeasible"):
        PricingEngine().price(impossible, identity_quote())
