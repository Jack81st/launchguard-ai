# Architecture

![LaunchGuard architecture](assets/architecture.svg)

## Workflow boundaries

LaunchGuard uses LangGraph for orchestration and durable human review. Currency resolution, policy retrieval, pricing, compliance, persistence, and delivery are deterministic services with explicit contracts. Listing generation is the only component that can call a model, and the default implementation is deterministic.

The graph executes:

1. `validate_evidence`
2. `resolve_fx`
3. `retrieve_policies`
4. `calculate_pricing`
5. `generate_listing`
6. `run_compliance`
7. `approval` or `blocked`
8. `publish` or `reject`

## Durable review boundary

The approval node calls LangGraph `interrupt()` with a JSON-serializable review package. The SQLite checkpointer stores graph position and state under a stable `thread_id`, which is also the LaunchGuard `run_id`. Resuming with `Command(resume=...)` re-enters the node, validates an `ApprovalDecision`, applies optional reviewer edits, records the decision, and continues to publish or reject.

All code before `interrupt()` in the approval node is side-effect free. Approval persistence occurs only after a resume value is returned and uses an idempotent upsert.

## Persistence model

Two SQLite databases keep responsibilities separate:

- `checkpoints.sqlite`: LangGraph checkpoints and pending interrupts;
- `launchguard.sqlite`: run snapshots, node events, approvals, and delivery receipts.

SQLite WAL mode supports the local single-service deployment. A production multi-instance deployment should replace both with PostgreSQL-backed implementations.

## Idempotent delivery strategy

Shopify `productCreate` is protected by layered duplicate controls:

1. completed delivery receipt keyed by `run_id`;
2. deterministic handle `lg-{sku}-{run_id_prefix}`;
3. remote product lookup by handle before creation;
4. Shopify metafields containing the full run ID and evidence IDs;
5. product status asserted as `DRAFT` before price update.

This design reduces duplicate creation after retries. It cannot provide a distributed exactly-once guarantee without a transactional outbox and stronger remote idempotency support.

## Trust boundaries

Catalog descriptions, source references, policy files, model output, API responses, and reviewer input are treated as untrusted at their boundaries. Pydantic rejects unknown fields, policy ingestion screens common instruction-injection patterns, HTML is escaped in deterministic generation, LLM output is schema-validated, and deterministic compliance runs after generation.
