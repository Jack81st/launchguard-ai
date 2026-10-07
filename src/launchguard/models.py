"""Validated contracts shared across workflow nodes and external adapters."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SkuEvidence(StrictModel):
    sku: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=3, max_length=180)
    description: str = Field(min_length=10, max_length=5000)
    vendor: str = Field(min_length=1, max_length=120)
    market: str = Field(default="US", pattern=r"^[A-Z]{2}$")
    source_currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    target_currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    unit_cost: Decimal = Field(gt=0)
    inbound_shipping: Decimal = Field(ge=0)
    fulfillment_cost: Decimal = Field(ge=0)
    duty_rate: Decimal = Field(ge=0, lt=1)
    platform_fee_rate: Decimal = Field(ge=0, lt=1)
    vat_rate: Decimal = Field(ge=0, lt=1)
    return_reserve_rate: Decimal = Field(ge=0, lt=1)
    ad_cost_rate: Decimal = Field(ge=0, lt=1)
    target_margin: Decimal = Field(gt=0, lt=1)
    competitor_price: Optional[Decimal] = Field(default=None, gt=0)
    source_reference: str = Field(default="operator-provided", max_length=500)

    @field_validator("sku")
    @classmethod
    def normalize_sku(cls, value: str) -> str:
        return value.upper().replace(" ", "-")


class FxQuote(StrictModel):
    base: str
    quote: str
    rate: Decimal = Field(gt=0)
    as_of: str
    provider: str
    source_url: str
    mode: Literal["live", "fallback", "identity"]


class Citation(StrictModel):
    document_id: str
    title: str
    market: str
    effective_date: str
    source_path: str
    chunk: str
    score: float


class CostBreakdown(StrictModel):
    product_cost: Decimal
    inbound_shipping: Decimal
    duty: Decimal
    fulfillment: Decimal
    fixed_cost: Decimal
    variable_rate: Decimal
    target_margin: Decimal


class PriceScenario(StrictModel):
    name: str
    fx_rate: Decimal
    return_reserve_rate: Decimal
    platform_fee_rate: Decimal
    minimum_price: Decimal


class PricingDecision(StrictModel):
    currency: str
    minimum_price: Decimal
    recommended_price: Decimal
    competitor_price: Optional[Decimal]
    commercially_feasible: bool
    rationale: List[str]
    cost_breakdown: CostBreakdown
    scenarios: List[PriceScenario]


class ListingDraft(StrictModel):
    title: str = Field(min_length=3, max_length=255)
    description_html: str = Field(min_length=20, max_length=10000)
    seo_title: str = Field(min_length=3, max_length=70)
    seo_description: str = Field(min_length=20, max_length=320)
    tags: List[str] = Field(min_length=1, max_length=20)
    price: Decimal = Field(gt=0)
    currency: str
    evidence_ids: List[str] = Field(min_length=1)
    generator: str


class ComplianceFinding(StrictModel):
    code: str
    severity: Literal["info", "warning", "blocker"]
    message: str
    field: Optional[str] = None


class ApprovalDecision(StrictModel):
    action: Literal["approve", "reject"]
    reviewer: str = Field(min_length=2, max_length=120)
    note: str = Field(default="", max_length=1000)
    edited_title: Optional[str] = Field(default=None, min_length=3, max_length=255)
    edited_description_html: Optional[str] = Field(default=None, min_length=20, max_length=10000)


class DeliveryReceipt(StrictModel):
    mode: Literal["dry-run", "live", "skipped"]
    status: Literal["prepared", "created", "duplicate", "rejected", "blocked"]
    run_id: str
    idempotency_key: str
    remote_id: Optional[str] = None
    handle: Optional[str] = None
    payload_hash: Optional[str] = None
    detail: str


class RunEvent(StrictModel):
    node: str
    status: Literal["started", "completed", "failed", "paused", "resumed"]
    duration_ms: int = Field(default=0, ge=0)
    detail: Dict[str, Any] = Field(default_factory=dict)
    occurred_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class RunRecord(StrictModel):
    run_id: str
    status: Literal[
        "running",
        "pending_approval",
        "approved",
        "rejected",
        "blocked",
        "completed",
        "failed",
    ]
    sku: str
    state: Dict[str, Any]
    created_at: str
    updated_at: str
