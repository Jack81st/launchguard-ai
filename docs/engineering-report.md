# LaunchGuard AI Engineering Report

## Executive summary

LaunchGuard AI is an original, evidence-first product launch workflow built from an empty repository. It converts operator-owned SKU economics into a policy-cited listing proposal, pauses at a durable human approval boundary, and prepares or creates an idempotent Shopify draft. The system is deliberately narrower than a generic multi-agent demo: every component exists to make a commercial decision inspectable, restart-safe, and difficult to publish accidentally.

The release candidate was verified with 34 automated tests, 83.76% branch-aware coverage, three passing evaluation cases, and a real browser acceptance run through the human approval checkpoint and Shopify dry-run receipt.

## Product and engineering decisions

### 1. Evidence before generation

The workflow begins with a strict `SKUInput` contract. Cost, logistics, fee, margin, market, vendor, and product facts are typed and validated before any generation occurs. Free text is treated as evidence, not as an instruction channel. Suspicious instruction-like payloads are blocked by deterministic compliance rules.

Why it matters: a polished description is not useful if its source assumptions are missing or its claims cannot be traced to operator-provided facts.

### 2. Durable approval is part of the graph

Human review is implemented with LangGraph `interrupt()` and SQLite checkpointing. The workflow uses a stable `thread_id`, persists an independent audit ledger, and resumes with `Command(resume=...)`. Delivery happens only after the resumed decision has been validated and recorded.

Why it matters: the approval is not a UI-only modal. The Python process can stop while a run is waiting and a later process can resume the exact checkpoint.

### 3. Deterministic services replace decorative agents

FX resolution, policy retrieval, pricing, compliance, persistence, and Shopify delivery are deterministic services. The only generative component is listing copy, which defaults to a deterministic generator and can be replaced by an OpenAI-compatible structured-output provider.

Why it matters: calculations and safety checks remain inspectable, reproducible, and testable instead of being hidden inside prompts.

### 4. Retrieval returns governance evidence

Policies are versioned Markdown documents with required IDs, markets, effective dates, and source paths. SQLite FTS5 retrieves chunks with citations, and the generator may cite only IDs present in the retrieved evidence set.

Why it matters: retrieval is used for decision provenance rather than decorative context stuffing.

### 5. Pricing exposes assumptions and stress

The pricing engine solves for the contribution-margin floor using converted unit cost, inbound shipping, duty, fulfillment, platform fees, VAT, returns reserve, advertising cost, and target margin. Every review package includes four scenarios:

1. base economics;
2. a 3% adverse FX movement;
3. a two-percentage-point increase in returns;
4. a one-percentage-point increase in platform fees.

Why it matters: the workflow can surface a commercially fragile proposal before copy approval or external delivery.

### 6. External delivery has a side-effect envelope

Shopify delivery is dry-run by default. Live mode requires explicit configuration, a validated `*.myshopify.com` domain, a scoped token, a recorded human approval, and zero compliance blockers. The connector uses a deterministic handle, local delivery ledger, remote lookup, `DRAFT` status assertion, and retry handling for rate limits and transient server failures.

Why it matters: retries and process restarts should not create duplicate products or silently publish a live listing.

## Workflow

```text
validate evidence
  → resolve FX
  → retrieve effective policies
  → calculate price floor and stress cases
  → generate a schema-valid listing
  → run deterministic compliance
  → interrupt for human review
  → reject or deliver an idempotent Shopify DRAFT
```

Compliance blockers route directly to a blocked terminal state. A rejection creates an audited rejected state. Approval resumes the checkpoint and enters the delivery boundary.

## Verified quality evidence

| Check | Verified result |
|---|---:|
| Automated tests | 34 passed |
| Branch-aware coverage | 83.76% |
| Bundled evaluation cases | 3/3 passed |
| Evaluation decision accuracy | 100% |
| Evaluation price-floor pass rate | 100% |
| Evaluation citation coverage | 100% |
| Browser acceptance path | Passed |
| Automatic live publishes in default mode | 0 |

The tests cover validation, CSV loading, live and fallback FX behavior, policy indexing and filtering, pricing calculations, schema-constrained generation, prompt-injection blocking, Shopify request behavior, duplicate prevention, workflow interruption, process-restart resume, API behavior, and the evaluation gate.

The evaluation set is intentionally small and transparent. Its percentages are regression metrics only; they should not be represented as business impact or model quality on an external benchmark.

## Security and failure controls

- strict Pydantic validation at input, approval, listing, and connector boundaries;
- prompt-injection pattern checks on operator text and generated content;
- HTML escaping in deterministic listing generation;
- policy effective-date and market filters;
- explicit warning when a dated fallback FX rate is used;
- no credential requirement in default mode;
- no live Shopify write without approval and live-mode configuration;
- GraphQL user errors and partial price-update failures fail closed;
- append-style node events plus separate approval and delivery records.

The complete abuse-case analysis is documented in the [threat model](threat-model.md).

## Originality and dependency posture

LaunchGuard was implemented from an empty repository and has its own product scope, contracts, workflow, services, UI, tests, documentation, and visual assets. It is not a fork and contains no copied source code, assets, Git history, or documentation from BorderPilot.

The project uses open-source dependencies through their documented public APIs. Its MIT license applies to LaunchGuard's original code; third-party packages retain their own licenses.

## Honest limitations

- The bundled policies are examples, not legal advice or a substitute for current marketplace terms.
- The bundled FX fallback is intentionally dated and must not be treated as a live quote.
- The system does not estimate demand, sales volume, or conversion.
- The current retrieval corpus and evaluation set are development fixtures, not production-scale evidence.
- Authentication, role-based access, encrypted secret storage, webhook reconciliation, observability export, and centralized audit retention remain future production work.
- Live Shopify behavior still requires validation against a development store owned or authorized by the operator.

## Reference implementation choices

The approval and persistence design follows the official LangGraph documentation for [interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) and [persistence](https://docs.langchain.com/oss/python/langgraph/persistence). Shopify delivery is designed around the official [`productCreate`](https://shopify.dev/docs/api/admin-graphql/latest/mutations/productCreate) mutation and Shopify's [idempotency guidance](https://shopify.dev/docs/api/usage/idempotent-requests). Live FX resolution uses the public [Frankfurter API](https://frankfurter.dev/), with explicit provenance and a warning-producing offline fallback.
