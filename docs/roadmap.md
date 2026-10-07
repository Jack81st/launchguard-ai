# Roadmap

The roadmap prioritizes reliability and operator evidence over adding more agents.

## 0.2 — Production foundations

- PostgreSQL checkpointer and audit ledger
- OIDC authentication and reviewer roles
- Managed-secret integration
- HTML allowlist sanitization
- Transactional delivery outbox and reconciliation
- Structured OpenTelemetry traces and cost/latency dashboards

## 0.3 — Connector ecosystem

- Shopify app authentication and store allowlists
- ERP and supplier adapters through a documented connector protocol
- Authorized marketplace and advertising data connectors
- FX and tax provider interfaces with freshness policies
- Webhook-based delivery reconciliation

## 0.4 — Evaluation and policy operations

- Versioned evaluation datasets with reviewer labels
- Retrieval precision and citation-grounding metrics
- Prompt regression and model comparison harness
- Policy ownership, expiry, approval, and change audit
- Per-market rule packs maintained independently of application releases

## Explicit non-goals

- Scraping marketplaces in violation of their terms
- Claiming sales or demand predictions from generic catalog APIs
- Autonomous live publication without accountable human review
- Increasing agent count as a proxy for product maturity
