import json
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from launchguard.connectors.shopify import (
    DryRunPublisher,
    ShopifyGraphQLPublisher,
    build_product_input,
)
from launchguard.models import ListingDraft
from launchguard.store import RunStore


def listing() -> ListingDraft:
    return ListingDraft(
        title="Insulated Travel Bottle",
        description_html="<p>Supported product description for a reviewed draft.</p>",
        seo_title="Insulated Travel Bottle",
        seo_description="A reviewed product draft with documented evidence and pricing.",
        tags=["launchguard-reviewed"],
        price=Decimal("29.99"),
        currency="USD",
        evidence_ids=["POLICY-1"],
        generator="test",
    )


def make_store(path: Path, run_id: str, sku: str) -> RunStore:
    store = RunStore(path)
    store.create_run(run_id, sku, {"run_id": run_id, "sku": {"sku": sku}})
    return store


def test_product_payload_is_always_draft(sku) -> None:
    payload = build_product_input("lg_1234567890", sku, listing())
    assert payload["status"] == "DRAFT"
    assert payload["handle"].startswith("lg-test-bottle-001-")
    assert any(field["key"] == "run_id" for field in payload["metafields"])


def test_dry_run_is_locally_idempotent(tmp_path: Path, sku) -> None:
    store = make_store(tmp_path / "runs.sqlite", "run-1", sku.sku)
    publisher = DryRunPublisher(store)
    first = publisher.publish("run-1", sku, listing())
    second = publisher.publish("run-1", sku, listing())
    assert first.status == "prepared"
    assert second.status == "duplicate"
    assert first.payload_hash == second.payload_hash
    store.close()


def test_live_publisher_creates_draft_then_sets_price(tmp_path: Path, sku) -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body["query"])
        if "ExistingProduct" in body["query"]:
            data = {"products": {"nodes": []}}
        elif "CreateDraft" in body["query"]:
            assert body["variables"]["product"]["status"] == "DRAFT"
            data = {
                "productCreate": {
                    "product": {
                        "id": "gid://shopify/Product/1",
                        "handle": body["variables"]["product"]["handle"],
                        "status": "DRAFT",
                        "variants": {"nodes": [{"id": "gid://shopify/ProductVariant/1"}]},
                    },
                    "userErrors": [],
                }
            }
        else:
            data = {
                "productVariantsBulkUpdate": {
                    "productVariants": [{"id": "gid://shopify/ProductVariant/1", "price": "29.99"}],
                    "userErrors": [],
                }
            }
        return httpx.Response(200, json={"data": data}, request=request)

    store = make_store(tmp_path / "runs.sqlite", "run-live", sku.sku)
    publisher = ShopifyGraphQLPublisher(
        store,
        "example.myshopify.com",
        "test-token",
        "2026-10",
        transport=httpx.MockTransport(handler),
    )
    receipt = publisher.publish("run-live", sku, listing())
    assert receipt.status == "created"
    assert receipt.remote_id == "gid://shopify/Product/1"
    assert len(calls) == 3
    assert publisher.publish("run-live", sku, listing()).status == "duplicate"
    store.close()


def test_remote_handle_lookup_prevents_duplicate(tmp_path: Path, sku) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        data = {
            "products": {
                "nodes": [
                    {
                        "id": "gid://shopify/Product/9",
                        "handle": "existing",
                        "status": "DRAFT",
                        "variants": {"nodes": [{"id": "gid://shopify/ProductVariant/9"}]},
                    }
                ]
            }
        }
        return httpx.Response(200, json={"data": data}, request=request)

    store = make_store(tmp_path / "runs.sqlite", "run-remote", sku.sku)
    publisher = ShopifyGraphQLPublisher(
        store,
        "example.myshopify.com",
        "test-token",
        "2026-10",
        transport=httpx.MockTransport(handler),
    )
    assert publisher.publish("run-remote", sku, listing()).status == "duplicate"
    store.close()


def test_live_publisher_requires_scoped_configuration(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "runs.sqlite")
    with pytest.raises(ValueError, match="requires"):
        ShopifyGraphQLPublisher(store, "", "", "2026-10")
    with pytest.raises(ValueError, match="myshopify"):
        ShopifyGraphQLPublisher(store, "example.com", "token", "2026-10")
    store.close()
