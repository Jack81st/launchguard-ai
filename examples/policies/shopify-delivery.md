---
id: SHOPIFY-DELIVERY-2026-03
title: Shopify Draft Delivery Control
market: GLOBAL
effective_date: 2026-03-10
---

## Safe delivery

The integration may create only unpublished Shopify products with DRAFT status. Live mode requires an explicit reviewer approval, a scoped Admin API token, a development or approved store domain, and a recorded audit event.

## Duplicate prevention

Each delivery must use a stable run identifier, deterministic product handle, local delivery ledger, and remote lookup before creation. Retrying a completed run must return the existing receipt instead of creating a second product.

## Failure handling

Retry only rate-limit responses and transient server failures. GraphQL user errors must be surfaced to the operator. A product created before a later price-update failure must remain a draft and the partial failure must be reported.
