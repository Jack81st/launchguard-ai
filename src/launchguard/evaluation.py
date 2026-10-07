"""Small, reproducible quality gate for pricing and compliance behavior."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from launchguard.connectors.fx import FxClient
from launchguard.models import SkuEvidence
from launchguard.services.compliance import ComplianceEngine, has_blockers
from launchguard.services.generation import DeterministicListingGenerator
from launchguard.services.policies import PolicyIndex
from launchguard.services.pricing import PricingEngine


def run_evaluation(policy_dir: Path, cases_path: Path) -> Dict[str, Any]:
    cases: List[Dict[str, Any]] = json.loads(cases_path.read_text(encoding="utf-8"))
    results: List[Dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as directory:
        index = PolicyIndex(Path(directory) / "eval-policies.sqlite")
        index.rebuild(policy_dir)
        pricing_engine = PricingEngine()
        generator = DeterministicListingGenerator()
        compliance = ComplianceEngine()
        fx_client = FxClient(mode="offline")
        for case in cases:
            sku = SkuEvidence.model_validate(case["sku"])
            fx = fx_client.quote(sku.source_currency, sku.target_currency)
            citations = index.search(
                f"{sku.title} {sku.description} pricing claims returns compliance",
                sku.market,
                limit=6,
            )
            pricing = pricing_engine.price(sku, fx)
            listing = generator.generate(sku, pricing, citations)
            findings = compliance.evaluate(sku, fx, pricing, listing, citations)
            blocked = has_blockers(findings)
            results.append(
                {
                    "id": case["id"],
                    "passed": blocked == case["expected_blocked"],
                    "expected_blocked": case["expected_blocked"],
                    "actual_blocked": blocked,
                    "price_floor_respected": listing.price >= pricing.minimum_price,
                    "citation_count": len(citations),
                    "finding_codes": [finding.code for finding in findings],
                }
            )
        index.close()
    passed = sum(result["passed"] for result in results)
    floors = sum(result["price_floor_respected"] for result in results)
    cited = sum(result["citation_count"] > 0 for result in results)
    count = len(results)
    return {
        "cases": count,
        "decision_accuracy": passed / count if count else 0,
        "price_floor_pass_rate": floors / count if count else 0,
        "citation_coverage": cited / count if count else 0,
        "passed": passed == count and floors == count and cited == count,
        "results": results,
    }
