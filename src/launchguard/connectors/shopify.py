"""Guarded Shopify GraphQL delivery with local and remote duplicate detection."""

from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any, Dict, Optional

import httpx

from launchguard.models import DeliveryReceipt, ListingDraft, SkuEvidence
from launchguard.store import RunStore


def _payload_hash(payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _handle(sku: str, run_id: str) -> str:
    safe = re.sub(r"[^a-z0-9]+", "-", sku.lower()).strip("-")
    return f"lg-{safe}-{run_id[:8]}"


def build_product_input(run_id: str, sku: SkuEvidence, listing: ListingDraft) -> Dict[str, Any]:
    return {
        "title": listing.title,
        "descriptionHtml": listing.description_html,
        "vendor": sku.vendor,
        "status": "DRAFT",
        "handle": _handle(sku.sku, run_id),
        "tags": listing.tags,
        "seo": {
            "title": listing.seo_title,
            "description": listing.seo_description,
        },
        "metafields": [
            {
                "namespace": "launchguard",
                "key": "run_id",
                "type": "single_line_text_field",
                "value": run_id,
            },
            {
                "namespace": "launchguard",
                "key": "evidence_ids",
                "type": "json",
                "value": json.dumps(listing.evidence_ids),
            },
        ],
    }


class DryRunPublisher:
    def __init__(self, store: RunStore) -> None:
        self.store = store

    def publish(self, run_id: str, sku: SkuEvidence, listing: ListingDraft) -> DeliveryReceipt:
        existing = self.store.get_delivery(run_id)
        if existing:
            return existing.model_copy(update={"status": "duplicate"})
        payload = build_product_input(run_id, sku, listing)
        receipt = DeliveryReceipt(
            mode="dry-run",
            status="prepared",
            run_id=run_id,
            idempotency_key=run_id,
            handle=payload["handle"],
            payload_hash=_payload_hash(payload),
            detail="Validated a Shopify draft payload without performing a network write.",
        )
        self.store.save_delivery(receipt)
        return receipt


class ShopifyGraphQLPublisher:
    def __init__(
        self,
        store: RunStore,
        shop: str,
        token: str,
        api_version: str,
        transport: Optional[httpx.BaseTransport] = None,
        max_attempts: int = 3,
    ) -> None:
        if not shop or not token:
            raise ValueError("Live Shopify mode requires a store domain and Admin API token")
        if not shop.endswith(".myshopify.com"):
            raise ValueError("Shopify store must be a *.myshopify.com domain")
        self.store = store
        self.shop = shop
        self.token = token
        self.api_version = api_version
        self.transport = transport
        self.max_attempts = max_attempts
        self.url = f"https://{shop}/admin/api/{api_version}/graphql.json"

    def _graphql(self, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        for attempt in range(1, self.max_attempts + 1):
            try:
                with httpx.Client(timeout=20, transport=self.transport) as client:
                    response = client.post(
                        self.url,
                        headers={
                            "Content-Type": "application/json",
                            "X-Shopify-Access-Token": self.token,
                        },
                        json={"query": query, "variables": variables},
                    )
                if response.status_code == 429 or response.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        "Retryable Shopify response", request=response.request, response=response
                    )
                response.raise_for_status()
                payload = response.json()
                if payload.get("errors"):
                    raise RuntimeError(f"Shopify GraphQL errors: {payload['errors']}")
                return payload["data"]
            except (httpx.HTTPError, KeyError, ValueError) as exc:
                if attempt == self.max_attempts:
                    raise RuntimeError(
                        f"Shopify request failed after {self.max_attempts} attempts"
                    ) from exc
                time.sleep(0.25 * (2 ** (attempt - 1)))
        raise AssertionError("Unreachable retry state")

    def publish(self, run_id: str, sku: SkuEvidence, listing: ListingDraft) -> DeliveryReceipt:
        existing = self.store.get_delivery(run_id)
        if existing:
            return existing.model_copy(update={"status": "duplicate"})

        product_input = build_product_input(run_id, sku, listing)
        handle = product_input["handle"]
        lookup = """
        query ExistingProduct($query: String!) {
          products(first: 1, query: $query) {
            nodes { id handle status variants(first: 1) { nodes { id } } }
          }
        }
        """
        matches = self._graphql(lookup, {"query": f"handle:{handle}"})["products"]["nodes"]
        if matches:
            receipt = DeliveryReceipt(
                mode="live",
                status="duplicate",
                run_id=run_id,
                idempotency_key=run_id,
                remote_id=matches[0]["id"],
                handle=handle,
                payload_hash=_payload_hash(product_input),
                detail="Found the existing remote draft by its deterministic handle.",
            )
            self.store.save_delivery(receipt)
            return receipt

        create_mutation = """
        mutation CreateDraft($product: ProductCreateInput!) {
          productCreate(product: $product) {
            product { id handle status variants(first: 1) { nodes { id } } }
            userErrors { field message }
          }
        }
        """
        created = self._graphql(create_mutation, {"product": product_input})["productCreate"]
        if created["userErrors"]:
            raise RuntimeError(f"Shopify productCreate rejected the draft: {created['userErrors']}")
        product = created["product"]
        if product["status"] != "DRAFT":
            raise RuntimeError("Shopify returned a non-draft product; delivery stopped")
        variant_id = product["variants"]["nodes"][0]["id"]

        price_mutation = """
        mutation SetDraftPrice($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
          productVariantsBulkUpdate(productId: $productId, variants: $variants) {
            productVariants { id price }
            userErrors { field message }
          }
        }
        """
        priced = self._graphql(
            price_mutation,
            {
                "productId": product["id"],
                "variants": [{"id": variant_id, "price": str(listing.price)}],
            },
        )["productVariantsBulkUpdate"]
        if priced["userErrors"]:
            raise RuntimeError(
                f"Draft was created but price update failed: {priced['userErrors']}"
            )

        receipt = DeliveryReceipt(
            mode="live",
            status="created",
            run_id=run_id,
            idempotency_key=run_id,
            remote_id=product["id"],
            handle=handle,
            payload_hash=_payload_hash(product_input),
            detail="Created an unpublished Shopify draft and set its initial variant price.",
        )
        self.store.save_delivery(receipt)
        return receipt
