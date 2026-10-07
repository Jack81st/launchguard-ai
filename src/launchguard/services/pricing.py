"""Transparent contribution-margin pricing with stress scenarios."""

from __future__ import annotations

from decimal import ROUND_CEILING, Decimal
from typing import List

from launchguard.models import (
    CostBreakdown,
    FxQuote,
    PriceScenario,
    PricingDecision,
    SkuEvidence,
)

MONEY = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY)


def _retail_round_up(value: Decimal) -> Decimal:
    whole = value.quantize(Decimal("1"), rounding=ROUND_CEILING)
    candidate = whole - Decimal("0.01")
    if candidate < value:
        candidate += Decimal("1")
    return candidate.quantize(MONEY)


class PricingEngine:
    def price(self, sku: SkuEvidence, fx: FxQuote) -> PricingDecision:
        product_cost = sku.unit_cost * fx.rate
        shipping = sku.inbound_shipping * fx.rate
        duty = (product_cost + shipping) * sku.duty_rate
        fixed_cost = product_cost + shipping + duty + sku.fulfillment_cost
        variable_rate = (
            sku.platform_fee_rate
            + sku.vat_rate
            + sku.return_reserve_rate
            + sku.ad_cost_rate
        )
        denominator = Decimal("1") - variable_rate - sku.target_margin
        if denominator <= 0:
            raise ValueError(
                "Pricing inputs are infeasible: variable costs plus target margin "
                "must be below 100%"
            )
        minimum = fixed_cost / denominator
        recommended = _retail_round_up(minimum)
        feasible = sku.competitor_price is None or recommended <= sku.competitor_price
        rationale = [
            f"Fixed landed cost is {_money(fixed_cost)} {sku.target_currency}.",
            f"Revenue-linked costs consume {(variable_rate * 100):.2f}% of gross price.",
            f"The target contribution margin is {(sku.target_margin * 100):.2f}%.",
        ]
        if sku.competitor_price is not None:
            relation = "within" if feasible else "above"
            rationale.append(
                f"The recommended price is {relation} the operator-provided competitor reference "
                f"of {_money(sku.competitor_price)} {sku.target_currency}."
            )

        scenarios: List[PriceScenario] = []
        for name, fx_multiplier, return_delta, fee_delta in (
            ("base", Decimal("1"), Decimal("0"), Decimal("0")),
            ("fx_stress_3pct", Decimal("1.03"), Decimal("0"), Decimal("0")),
            ("returns_stress_2pp", Decimal("1"), Decimal("0.02"), Decimal("0")),
            ("platform_fee_stress_1pp", Decimal("1"), Decimal("0"), Decimal("0.01")),
        ):
            scenario_fx = fx.rate * fx_multiplier
            scenario_fixed = (
                sku.unit_cost * scenario_fx
                + sku.inbound_shipping * scenario_fx
                + (sku.unit_cost * scenario_fx + sku.inbound_shipping * scenario_fx)
                * sku.duty_rate
                + sku.fulfillment_cost
            )
            scenario_variable = variable_rate + return_delta + fee_delta
            scenario_denominator = Decimal("1") - scenario_variable - sku.target_margin
            scenario_minimum = (
                scenario_fixed / scenario_denominator
                if scenario_denominator > 0
                else Decimal("999999")
            )
            scenarios.append(
                PriceScenario(
                    name=name,
                    fx_rate=scenario_fx,
                    return_reserve_rate=sku.return_reserve_rate + return_delta,
                    platform_fee_rate=sku.platform_fee_rate + fee_delta,
                    minimum_price=_money(scenario_minimum),
                )
            )

        return PricingDecision(
            currency=sku.target_currency,
            minimum_price=_money(minimum),
            recommended_price=recommended,
            competitor_price=sku.competitor_price,
            commercially_feasible=feasible,
            rationale=rationale,
            cost_breakdown=CostBreakdown(
                product_cost=_money(product_cost),
                inbound_shipping=_money(shipping),
                duty=_money(duty),
                fulfillment=_money(sku.fulfillment_cost),
                fixed_cost=_money(fixed_cost),
                variable_rate=variable_rate,
                target_margin=sku.target_margin,
            ),
            scenarios=scenarios,
        )
