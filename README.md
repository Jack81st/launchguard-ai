<div align="center">

# LaunchGuard AI

**A durable, evidence-first workflow that turns SKU economics into reviewed Shopify drafts.**

[![Python 3.9–3.12](https://img.shields.io/badge/Python-3.9%E2%80%933.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/Workflow-LangGraph-1C3C3C)](https://github.com/langchain-ai/langgraph)
[![CI](https://github.com/Jack81st/launchguard-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/Jack81st/launchguard-ai/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-gated%20at%2080%25-22C55E)](#quality-evidence)
[![Shopify](https://img.shields.io/badge/Shopify-DRAFT%20only-7AB55C?logo=shopify&logoColor=white)](#shopify-safety)
[![License: MIT](https://img.shields.io/badge/License-MIT-F59E0B.svg)](LICENSE)

[Quickstart](#quickstart) · [Architecture](docs/architecture.md) · [Engineering Report](docs/engineering-report.md) · [Threat Model](docs/threat-model.md) · [Roadmap](docs/roadmap.md) · [Contributing](CONTRIBUTING.md)

</div>

---

## The problem

Product teams often jump from a supplier row to generated copy without preserving the commercial assumptions, policy evidence, or human decision that justified the launch. LaunchGuard makes that chain explicit:

```text
operator-owned SKU evidence
→ sourced FX rate
→ versioned policy citations
→ contribution-margin scenarios
→ structured listing draft
→ deterministic compliance checks
→ durable human review
→ idempotent Shopify DRAFT
```

This is intentionally **not** a market-demand oracle. It does not pretend that a generic public product API can estimate Amazon sales. The workflow starts with data the operator owns, records every assumption, and stops safely when evidence or approval is missing.

<img src="docs/assets/architecture.svg" alt="LaunchGuard architecture and durable review boundary" width="100%" />

## What is materially different

| Design choice | Implementation | Operational value |
|---|---|---|
| Real human-in-the-loop | LangGraph `interrupt()` plus SQLite checkpoints and stable thread IDs | A run can pause, survive process restart, and resume after review |
| Services, not fake agents | FX, pricing, retrieval, compliance, persistence, and delivery are deterministic services | Business rules remain inspectable and testable |
| Operator-owned evidence | Strict CSV/JSON SKU contract with source reference | Avoids presenting demo catalog data as market intelligence |
| Versioned policy retrieval | SQLite FTS5, market filters, effective dates, source paths, and citation IDs | Reviewers can inspect exactly which rule supported the draft |
| Unit economics | Duty, shipping, fulfillment, fees, VAT, returns, ads, margin, FX, and four stress scenarios | Makes commercial feasibility visible before copy is approved |
| Safe delivery | Dry-run default, explicit review, deterministic handle, remote lookup, local ledger, Shopify `DRAFT` status | Reduces accidental publishing and duplicate products |
| Evaluation gate | Reproducible cases for clean launches, commercial warnings, and prompt-injection blocking | Changes can be measured instead of judged only by demos |

## Control room

<img src="docs/assets/review-screen.png" alt="LaunchGuard web control room showing a real workflow paused for human approval" width="100%" />

The web UI is the real local application, not a conceptual mockup. It starts workflows, displays pricing and FX provenance, renders policy citations and compliance findings, and resumes a paused run after approval or rejection.

## Quickstart

### Local Python

```bash
git clone https://github.com/Jack81st/launchguard-ai.git
cd launchguard-ai
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
launchguard serve
```

Open [http://127.0.0.1:8080](http://127.0.0.1:8080). The default configuration needs no LLM or Shopify credentials.

### Docker

```bash
docker compose up --build
```

SQLite run history and checkpoints are stored in the `launchguard-data` volume.

## Durable CLI review

Start an offline demonstration run:

```bash
launchguard start \
  --catalog examples/catalog.csv \
  --sku LG-BTL-001 \
  --offline
```

The command returns a `run_id` and exits with `pending_approval`. The process can now stop. Resume the same checkpoint later:

```bash
launchguard decide \
  --run-id lg_your_run_id \
  --action approve \
  --reviewer "Operations reviewer" \
  --note "Evidence, margin floor, and policy citations reviewed"
```

Reusing a completed `run_id` does not create another delivery.

## Pricing model

LaunchGuard solves the price required to preserve the target contribution margin:

```text
fixed cost = converted product cost + converted inbound shipping + duty + fulfillment

minimum price = fixed cost /
  (1 - platform fee - VAT - returns reserve - ad cost - target margin)
```

Each review includes:

- base economics;
- 3% adverse FX movement;
- +2 percentage points in returns;
- +1 percentage point in platform fees.

The model is decision support, not a forecast. It intentionally exposes every input instead of hiding them behind an agent prompt.

## Policy retrieval and generation

Policies are Markdown files with required metadata:

```yaml
---
id: PRICING-GOVERNANCE-2026-02
title: Contribution Margin and Pricing Governance
market: GLOBAL
effective_date: 2026-02-01
---
```

SQLite FTS5 retrieves market-appropriate chunks and returns document ID, effective date, source path, content, and score. The deterministic generator is used by default. An optional OpenAI-compatible endpoint can be enabled, but its JSON output is schema-validated and may cite only retrieved evidence IDs.

## Shopify safety

Live delivery is unavailable unless all of these conditions are true:

1. deterministic checks report no blockers;
2. the graph is resumed with an explicit named reviewer decision;
3. `LAUNCHGUARD_SHOPIFY_MODE=live` is configured;
4. a valid `*.myshopify.com` domain and Admin API token are present.

The connector then:

- checks the local delivery ledger;
- looks up the deterministic handle remotely;
- creates a product with `DRAFT` status only;
- updates the initial variant price;
- records the remote ID, handle, payload hash, and receipt.

Rate limits and transient server failures are retried. GraphQL user errors and partial price-update failures are surfaced rather than converted into success.

## Quality evidence

```bash
make lint
make test
make eval
```

CI runs on Python 3.9, 3.11, and 3.12, enforces at least 80% branch-aware coverage, executes the evaluation gate, and builds the production container. Tests use mock transports and never need paid credentials.

Verified locally on the release candidate:

- 34 automated tests passing;
- 83.76% branch-aware coverage;
- 3/3 evaluation cases passing;
- 100% decision accuracy, pricing-floor pass rate, and citation coverage on the bundled evaluation set;
- one real browser acceptance path from evidence intake to checkpointed approval and idempotent Shopify dry-run receipt.

These are repository quality metrics, not claims about commercial lift. The small bundled evaluation is a regression gate, not a production benchmark. It reports:

- decision accuracy;
- pricing-floor pass rate;
- policy citation coverage;
- per-case compliance codes.

See the [engineering report](docs/engineering-report.md) for the design rationale, verification scope, and known limitations.

## API

FastAPI exposes:

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/runs` | Validate evidence and run until completion or review interrupt |
| `GET` | `/api/runs` | List recent runs |
| `GET` | `/api/runs/{run_id}` | Read persisted state and audit events |
| `POST` | `/api/runs/{run_id}/decision` | Resume a pending checkpoint with approve/reject and optional edits |
| `GET` | `/health` | Container and service health |

Interactive OpenAPI documentation is available at `/docs`.

## Repository layout

```text
src/launchguard/
├── api.py                    # FastAPI and control-room API
├── workflow.py               # LangGraph, interrupt, resume, checkpointing
├── models.py                 # Strict evidence and output contracts
├── store.py                  # Run, event, approval, and delivery ledger
├── connectors/
│   ├── catalog.py            # Operator-owned CSV evidence
│   ├── fx.py                 # Live FX with explicit fallback provenance
│   └── shopify.py            # Guarded GraphQL draft delivery
└── services/
    ├── policies.py           # Versioned FTS5 retrieval
    ├── pricing.py            # Unit economics and stress scenarios
    ├── generation.py         # Deterministic and optional LLM generation
    └── compliance.py         # Deterministic safety and policy checks
```

## Honest boundaries

- Bundled policy files are examples, not legal advice or current marketplace terms.
- The fallback FX table is deliberately dated and raises a warning.
- The project does not estimate demand, sales, or conversion.
- Live Shopify behavior requires a development store and should be tested there first.
- Authentication, RBAC, encrypted secrets, and centralized audit retention remain required before multi-user production use.

## Originality and license

LaunchGuard is an original implementation created from an empty repository. It is not a fork and contains no source code, assets, Git history, or documentation copied from BorderPilot. It uses established open-source libraries through their public APIs and is released under the [MIT License](LICENSE).
