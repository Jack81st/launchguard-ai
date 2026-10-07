from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from launchguard.config import Settings
from launchguard.models import SkuEvidence
from launchguard.workflow import LaunchWorkflow

ROOT = Path(__file__).parents[1]


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        database_path=tmp_path / "launchguard.sqlite",
        checkpoint_path=tmp_path / "checkpoints.sqlite",
        policy_dir=ROOT / "examples" / "policies",
        fx_mode="offline",
        shopify_mode="dry-run",
    )


@pytest.fixture
def sku() -> SkuEvidence:
    return SkuEvidence(
        sku="test bottle 001",
        title="Insulated Travel Bottle",
        description="A stainless-steel bottle with a locking lid and replaceable seal.",
        vendor="Test Supply",
        market="US",
        source_currency="USD",
        target_currency="USD",
        unit_cost=Decimal("8.20"),
        inbound_shipping=Decimal("2.10"),
        fulfillment_cost=Decimal("4.20"),
        duty_rate=Decimal("0"),
        platform_fee_rate=Decimal("0.029"),
        vat_rate=Decimal("0"),
        return_reserve_rate=Decimal("0.06"),
        ad_cost_rate=Decimal("0.12"),
        target_margin=Decimal("0.25"),
        competitor_price=Decimal("34.99"),
        source_reference="test-fixture",
    )


@pytest.fixture
def workflow(settings: Settings) -> LaunchWorkflow:
    instance = LaunchWorkflow(settings)
    yield instance
    instance.close()


@pytest.fixture
def live_settings(settings: Settings) -> Settings:
    return replace(
        settings,
        shopify_mode="live",
        shopify_store="example.myshopify.com",
        shopify_token="test-token",
    )
