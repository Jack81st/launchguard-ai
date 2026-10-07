"""Deterministic policy and safety checks around generated copy."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Iterable, List

from launchguard.models import (
    Citation,
    ComplianceFinding,
    FxQuote,
    ListingDraft,
    PricingDecision,
    SkuEvidence,
)
from launchguard.services.policies import contains_prompt_injection

PROHIBITED_CLAIMS = {
    "guaranteed results": "Unsupported guarantee",
    "cures": "Medical cure claim",
    "risk-free": "Absolute risk claim",
    "best on the market": "Unsubstantiated superlative",
}


class ComplianceEngine:
    def evaluate(
        self,
        sku: SkuEvidence,
        fx: FxQuote,
        pricing: PricingDecision,
        listing: ListingDraft,
        citations: Iterable[Citation],
    ) -> List[ComplianceFinding]:
        findings: List[ComplianceFinding] = []
        citation_list = list(citations)
        combined_input = f"{sku.title}\n{sku.description}\n{sku.source_reference}"
        combined_output = f"{listing.title}\n{listing.description_html}"

        if contains_prompt_injection(combined_input):
            findings.append(
                ComplianceFinding(
                    code="UNTRUSTED_INSTRUCTION",
                    severity="blocker",
                    field="description",
                    message="Catalog evidence contains a prompt-injection pattern.",
                )
            )
        if not citation_list:
            findings.append(
                ComplianceFinding(
                    code="NO_POLICY_EVIDENCE",
                    severity="blocker",
                    message="No applicable policy citation was retrieved.",
                )
            )
        if listing.price < pricing.minimum_price:
            findings.append(
                ComplianceFinding(
                    code="BELOW_PRICE_FLOOR",
                    severity="blocker",
                    field="price",
                    message="The listing price is below the calculated contribution-margin floor.",
                )
            )
        if not pricing.commercially_feasible:
            findings.append(
                ComplianceFinding(
                    code="ABOVE_COMPETITOR_REFERENCE",
                    severity="warning",
                    field="price",
                    message="The viable price exceeds the operator-provided competitor reference.",
                )
            )
        if fx.mode == "fallback":
            findings.append(
                ComplianceFinding(
                    code="FX_FALLBACK",
                    severity="warning",
                    message="Pricing used a dated fallback FX rate; refresh before live approval.",
                )
            )
        for phrase, label in PROHIBITED_CLAIMS.items():
            if phrase in combined_output.lower():
                findings.append(
                    ComplianceFinding(
                        code="PROHIBITED_CLAIM",
                        severity="blocker",
                        field="description_html",
                        message=f"{label}: {phrase!r}.",
                    )
                )
        if len(listing.seo_title) > 70:
            findings.append(
                ComplianceFinding(
                    code="SEO_TITLE_LENGTH",
                    severity="warning",
                    field="seo_title",
                    message="SEO title exceeds 70 characters.",
                )
            )
        if re.search(r"<script|javascript:", listing.description_html, flags=re.IGNORECASE):
            findings.append(
                ComplianceFinding(
                    code="UNSAFE_HTML",
                    severity="blocker",
                    field="description_html",
                    message="Listing HTML contains an unsafe executable construct.",
                )
            )
        if listing.price <= Decimal("0"):
            findings.append(
                ComplianceFinding(
                    code="INVALID_PRICE",
                    severity="blocker",
                    field="price",
                    message="Listing price must be positive.",
                )
            )
        if not findings:
            findings.append(
                ComplianceFinding(
                    code="CHECKS_PASSED",
                    severity="info",
                    message="All deterministic launch checks passed.",
                )
            )
        return findings


def has_blockers(findings: Iterable[ComplianceFinding]) -> bool:
    return any(finding.severity == "blocker" for finding in findings)
